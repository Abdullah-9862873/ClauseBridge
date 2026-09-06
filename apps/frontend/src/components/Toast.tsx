'use client';

import { useToast } from '@/lib/toast-context';

export default function ToastContainer() {
  const { toasts, removeToast } = useToast();

  if (toasts.length === 0) return null;

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          <div className="toast-body">
            <p className="toast-message">{toast.message}</p>
            <div className="toast-actions">
              {toast.onRetry && (
                <button
                  className="toast-btn toast-btn-retry"
                  onClick={() => {
                    toast.onRetry!();
                    removeToast(toast.id);
                  }}
                >
                  Retry
                </button>
              )}
              {toast.onNavigate && (
                <button
                  className="toast-btn toast-btn-navigate"
                  onClick={() => {
                    toast.onNavigate!();
                    removeToast(toast.id);
                  }}
                >
                  {toast.navigateLabel || 'Go to page'}
                </button>
              )}
            </div>
          </div>
          <button
            className="toast-close"
            onClick={() => removeToast(toast.id)}
            aria-label="Close"
          >
            &times;
          </button>
        </div>
      ))}
    </div>
  );
}
