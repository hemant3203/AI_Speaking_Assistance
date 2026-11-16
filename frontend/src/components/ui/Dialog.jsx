/** Confirmation dialog on the native <dialog>, which brings focus trapping and Esc for free. */
import { useEffect, useRef } from 'react';

export function Dialog({ open, onClose, title, children }) {
  const ref = useRef(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      aria-labelledby="dialog-title"
      className="card m-auto w-[calc(100vw-2rem)] max-w-md p-6 text-ink"
    >
      {open && (
        <>
          <h2 id="dialog-title" className="text-xl font-bold">
            {title}
          </h2>
          <div className="mt-3">{children}</div>
        </>
      )}
    </dialog>
  );
}
