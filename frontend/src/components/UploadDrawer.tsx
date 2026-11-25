import { useEffect } from "react";
import UploadPanel from "./UploadPanel";

/** Side panel with the CSV upload flow, opened from the Feedback page. */
export default function UploadDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", onKey); document.body.style.overflow = prev; };
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="drawer" role="dialog" aria-modal="true" aria-label="Upload a CSV" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className="drawer__panel">
        <header className="drawer__head">
          <div><p className="sec__eyebrow">Your own data</p><h2>Upload a CSV of reviews</h2><p className="gcard__sub">The engine checks the file, reads every review with AI, and shows themes, sentiment, Return / Non-Return, insights and opportunities.</p></div>
          <button type="button" className="drawer__close" onClick={onClose} aria-label="Close">×</button>
        </header>
        <div className="drawer__list"><UploadPanel title={false} /></div>
      </div>
    </div>
  );
}
