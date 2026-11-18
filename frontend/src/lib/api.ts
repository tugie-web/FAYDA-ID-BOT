declare global {
  interface Window {
    Telegram?: {
      WebApp?: {
        initData?: string;
        ready?: () => void;
        expand?: () => void;
      };
    };
  }
}

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

function telegramHeaders(): HeadersInit {
  const initData = window.Telegram?.WebApp?.initData;
  if (!initData) {
    throw new Error("Please open this service inside the official Telegram Mini App.");
  }
  return {
    "Content-Type": "application/json",
    Authorization: `tma ${initData}`,
  };
}

export type ServiceOrder = {
  order_id: string;
  service_code: string;
  amount: string;
  currency: string;
  status: string;
};

export async function createOrder(serviceCode: string): Promise<ServiceOrder> {
  const response = await fetch(`${API_BASE}/api/v1/orders`, {
    method: "POST",
    headers: telegramHeaders(),
    body: JSON.stringify({ service_code: serviceCode }),
  });
  if (!response.ok) throw new Error(await responseError(response));
  return response.json();
}

export async function submitPayment(
  orderId: number,
  provider: "cbe" | "telebirr" | "cbebirr",
  transactionReference: string,
) {
  const response = await fetch(`${API_BASE}/api/v1/orders/${orderId}/payments`, {
    method: "POST",
    headers: telegramHeaders(),
    body: JSON.stringify({ provider, transaction_reference: transactionReference }),
  });
  if (!response.ok) throw new Error(await responseError(response));
  return response.json();
}

async function responseError(response: Response): Promise<string> {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : "The request could not be completed.";
  } catch {
    return "The request could not be completed.";
  }
}

export {};
