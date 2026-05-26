export interface ConveySettings {
  showReasoning: boolean;
  showToolCalls: boolean;
  reasoningEffort: 'high' | 'max';
  model: 'deepseek-v4-flash' | 'deepseek-v4-pro';
}

const PREFIX = 'convey_settings_';

const DEFAULTS: ConveySettings = {
  showReasoning: false,
  showToolCalls: false,
  reasoningEffort: 'high',
  model: 'deepseek-v4-flash',
};

export function loadSettings(): ConveySettings {
  const s = { ...DEFAULTS };
  for (const key of Object.keys(DEFAULTS) as (keyof ConveySettings)[]) {
    const v = localStorage.getItem(`${PREFIX}${key}`);
    if (v !== null) {
      if (key === 'showReasoning' || key === 'showToolCalls') {
        (s as Record<string, unknown>)[key] = v === 'true';
      } else {
        (s as Record<string, unknown>)[key] = v;
      }
    }
  }
  return s;
}

function saveSetting<K extends keyof ConveySettings>(key: K, value: ConveySettings[K]) {
  localStorage.setItem(`${PREFIX}${key}`, String(value));
}

interface SettingsPanelProps {
  open: boolean;
  onClose: () => void;
  settings: ConveySettings;
  onSettingsChange: (s: ConveySettings) => void;
}

export default function SettingsPanel({ open, onClose, settings, onSettingsChange }: SettingsPanelProps) {
  const update = <K extends keyof ConveySettings>(key: K, value: ConveySettings[K]) => {
    saveSetting(key, value);
    onSettingsChange({ ...settings, [key]: value });
  };

  return (
    <>
      {open && <div className="settings-overlay" onClick={onClose} />}
      <div className={`settings-panel${open ? ' open' : ''}`}>
        <div className="settings-header">
          <span className="settings-title">设置</span>
          <button className="settings-close" onClick={onClose}>✕</button>
        </div>

        <div className="settings-body">
          <label className="settings-toggle-row">
            <span className="settings-label">推理过程展示</span>
            <span className={`toggle-switch${settings.showReasoning ? ' on' : ''}`}>
              <input
                type="checkbox"
                checked={settings.showReasoning}
                onChange={e => update('showReasoning', e.target.checked)}
              />
              <span className="toggle-thumb" />
            </span>
          </label>

          <label className="settings-toggle-row">
            <span className="settings-label">工具调用展示</span>
            <span className={`toggle-switch${settings.showToolCalls ? ' on' : ''}`}>
              <input
                type="checkbox"
                checked={settings.showToolCalls}
                onChange={e => update('showToolCalls', e.target.checked)}
              />
              <span className="toggle-thumb" />
            </span>
          </label>

          <div className="settings-select-row">
            <label className="settings-label">推理强度</label>
            <select
              className="settings-select"
              value={settings.reasoningEffort}
              onChange={e => update('reasoningEffort', e.target.value as 'high' | 'max')}
            >
              <option value="high">高</option>
              <option value="max">最大</option>
            </select>
          </div>

          <div className="settings-select-row">
            <label className="settings-label">模型</label>
            <select
              className="settings-select"
              value={settings.model}
              onChange={e => update('model', e.target.value as 'deepseek-v4-flash' | 'deepseek-v4-pro')}
            >
              <option value="deepseek-v4-flash">Flash 快速</option>
              <option value="deepseek-v4-pro">Pro 深度</option>
            </select>
          </div>
        </div>
      </div>
    </>
  );
}
