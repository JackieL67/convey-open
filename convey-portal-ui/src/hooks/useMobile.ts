import { useState, useEffect } from 'react';

interface MobileState {
  isMobile: boolean;
  isTouch: boolean;
  viewportHeight: number;
}

function getState(): MobileState {
  const isTouch = 'ontouchstart' in window || navigator.maxTouchPoints > 0;
  const vp = window.visualViewport;
  const viewportHeight = vp ? vp.height : window.innerHeight;
  const isMobile = window.innerWidth < 640 || isTouch;
  return { isMobile, isTouch, viewportHeight };
}

export function useMobile(): MobileState {
  const [state, setState] = useState<MobileState>(getState);

  useEffect(() => {
    const update = () => setState(getState());

    window.addEventListener('resize', update);
    window.visualViewport?.addEventListener('resize', update);
    window.visualViewport?.addEventListener('scroll', update);

    return () => {
      window.removeEventListener('resize', update);
      window.visualViewport?.removeEventListener('resize', update);
      window.visualViewport?.removeEventListener('scroll', update);
    };
  }, []);

  return state;
}
