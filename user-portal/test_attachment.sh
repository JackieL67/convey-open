#!/usr/bin/env bash
# ============================================================
# Convey 附件上传+聊天 集成测试
# 用法:
#   bash test_attachment.sh              # 默认 3001 (调试)
#   bash test_attachment.sh 3000         # 指定端口
#   PORT=3000 bash test_attachment.sh    # 或环境变量
#
# 依赖: curl, python3
# ============================================================
set -euo pipefail

PORT="${1:-${PORT:-3001}}"
BASE="http://localhost:${PORT}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TEST_USER="test@example.com"
DEVICE_ID="test-$(date +%s)"
TMP_DIR="/tmp/convey-test-$$"
PASS=0
FAIL=0

# ── 颜色 ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cleanup() {
    rm -rf "$TMP_DIR"
}
trap cleanup EXIT
mkdir -p "$TMP_DIR"

# ── 工具函数 ──
pass() { echo -e "  ${GREEN}✅ $1${NC}"; PASS=$((PASS+1)); }
fail() { echo -e "  ${RED}❌ $1${NC}"; FAIL=$((FAIL+1)); }
info() { echo -e "  ${YELLOW}ℹ️  $1${NC}"; }

report() {
    echo ""
    echo "══════════════════════════════════════"
    echo -e "  通过: ${GREEN}${PASS}${NC}   失败: ${RED}${FAIL}${NC}"
    if [ "$FAIL" -eq 0 ]; then
        echo -e "  ${GREEN}全部通过 ✅${NC}"
    else
        echo -e "  ${RED}有 ${FAIL} 项失败，请排查${NC}"
    fi
    echo "══════════════════════════════════════"
    return $FAIL
}

# ── 1. 服务器可达 ──
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Convey 附件集成测试 (端口 ${PORT})"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo ""
echo "── 1. 服务器可达 ──"
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/" 2>&1 || echo "000")
if [ "$HTTP_CODE" = "200" ] || [ "$HTTP_CODE" = "302" ]; then
    pass "服务器 ${BASE} 可达 (HTTP ${HTTP_CODE})"
else
    fail "服务器 ${BASE} 无响应 (HTTP ${HTTP_CODE})"
    report; exit 1
fi

health=$(curl -s "${BASE}/api/health" 2>/dev/null || echo '{}')
status=$(python3 -c "import sys,json; print(json.loads(sys.argv[1]).get('status','unknown'))" "$health" 2>/dev/null || echo "unknown")
if [ "$status" = "ok" ] || [ "$status" = "degraded" ]; then
    pass "健康检查: ${status}"
else
    fail "健康检查异常: ${status}"
fi

# ── 2. 认证 ──
echo ""
echo "── 2. 认证 ──"
AUTH_RESP=$(curl -s -X POST "${BASE}/api/auth" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${TEST_USER}\",\"device_id\":\"${DEVICE_ID}\"}")
TOKEN=$(python3 -c "import sys,json; print(json.loads(sys.argv[1]).get('token',''))" "$AUTH_RESP" 2>/dev/null || echo "")
if [ -n "$TOKEN" ]; then
    pass "认证成功 (email: ${TEST_USER})"
else
    fail "认证失败: $(echo "$AUTH_RESP" | python3 -c 'import sys,json; d=json.loads(sys.stdin.read()); print(d.get("detail", d.get("need_invite","未知错误")))' 2>/dev/null || echo "$AUTH_RESP")"
    report; exit 1
fi

# ── 3. 上传文件 ──
echo ""
echo "── 3. 上传文件 ──"

# 创建测试文件（模拟图片）
echo "FAKE_PNG_DATA_$(date +%s)" > "${TMP_DIR}/test-image.png"

UPLOAD=$(curl -s -X POST "${BASE}/api/upload" \
    -H "Authorization: Bearer ${TOKEN}" \
    -F "file=@${TMP_DIR}/test-image.png")

FILE_ID=$(python3 -c "import sys,json; print(json.loads(sys.argv[1]).get('file_id',''))" "$UPLOAD" 2>/dev/null || echo "")
URL=$(python3 -c "import sys,json; print(json.loads(sys.argv[1]).get('url',''))" "$UPLOAD" 2>/dev/null || echo "")

if [ -n "$FILE_ID" ]; then
    pass "上传成功: ${FILE_ID}"
else
    fail "上传失败: $(echo "$UPLOAD" | head -c 200)"
fi

# ── 4. 无 token 访问文件（Bug #2 修复验证） ──
echo ""
echo "── 4. 无 token 访问文件 (Bug #2) ──"
FILE_HTTP=$(curl -s -o /dev/null -w "%{http_code}" "${BASE}/api/files/${FILE_ID}" 2>&1 || echo "000")
if [ "$FILE_HTTP" = "200" ]; then
    pass "公开访问返回 200 (之前 401)"
else
    fail "公开访问返回 ${FILE_HTTP}，期望 200"
fi

# ── 5. 带附件的聊天（Bug #1 修复验证） ──
echo ""
echo "── 5. 带附件聊天 (Bug #1) ──"

# SSE 流式请求，提取最终响应
SSE_RESP=$(curl -s -X POST "${BASE}/api/chat" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"email\":\"${TEST_USER}\",
        \"message\":\"你好，只回复OK两个字母，不要其他内容\",
        \"settings\":{\"reasoning_level\":\"auto\",\"reply_style\":\"default\",\"model\":\"\"},
        \"attachments\":[{\"file_id\":\"${FILE_ID}\",\"filename\":\"test-image.png\",\"content_type\":\"image/png\"}]
    }" 2>&1)

# 检查是否有 content_type 错误
if echo "$SSE_RESP" | grep -qi "object has no attribute"; then
    fail "流式响应出现 AttributeError (Bug #1 未修复)"
elif echo "$SSE_RESP" | grep -q "event: done"; then
    # 提取 done 事件中的 response（awk 取 'event: done' 下一行的 data: JSON）
    RESPONSE=$(echo "$SSE_RESP" | awk '/^event: done$/{getline; print}' | \
        python3 -c "import sys,json; d=json.loads(sys.stdin.read().strip()[6:]); print(d.get('response','')[:100])" 2>/dev/null || echo "")
    if [ -n "$RESPONSE" ]; then
        pass "聊天成功: ${RESPONSE}"
    else
        info "聊天似乎成功但未能解析响应"
        pass "聊天成功 (done 事件存在)"
    fi
else
    fail "聊天异常: $(echo "$SSE_RESP" | tail -5)"
fi

# ── 6. 无附件聊天（回归测试） ──
echo ""
echo "── 6. 无附件聊天 (回归) ──"
SSE2=$(curl -s -X POST "${BASE}/api/chat" \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Content-Type: application/json" \
    -d "{
        \"email\":\"${TEST_USER}\",
        \"message\":\"Hi\",
        \"settings\":{\"reasoning_level\":\"auto\",\"reply_style\":\"default\",\"model\":\"\"}
    }" 2>&1)

if echo "$SSE2" | grep -q "event: done"; then
    pass "无附件聊天正常"
else
    fail "无附件聊天异常"
fi

# ── 完成 ──
report
