declare global {
  interface Window {
    Fintoc?: {
      create: (options: {
        publicKey: string;
        product: string;
        country: string;
        holderType?: string;
        webhookUrl?: string;
        onSuccess: () => void;
        onExit: () => void;
        onEvent?: (eventName: string, metadata?: unknown) => void;
      }) => { open: () => void };
    };
  }
}

export {};
