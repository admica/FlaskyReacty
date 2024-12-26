declare global {
  interface Window {
    addDebugMessage?: (message: string) => void;
  }
}

export {}; 