import { useEffect } from "react";
import type { ReactNode } from "react";

type ModalProps = {
    open: boolean;
    title: string;
    onClose: () => void;
    children: ReactNode;
    position?: "center" | "side";
    size?: "default" | "large";
};

export default function Modal({
    open,
    title,
    onClose,
    children,
    position = "center",
    size = "default",
}: ModalProps) {
    useEffect(() => {
        if (!open) return;
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") onClose();
        };
        window.addEventListener("keydown", onKeyDown);
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [open, onClose]);

    if (!open) return null;

    const overlayClass =
        position === "center" ? "modal-overlay modal-overlay-center" : "modal-overlay";
    const boxClass = [
        position === "center" ? "modal-box modal-box-center" : "modal-box",
        size === "large" ? "modal-box-large" : "",
    ].join(" ").trim();

    return (
        <div className={overlayClass} onClick={onClose}>
            <div className={boxClass} onClick={e => e.stopPropagation()}>
                <div className="modal-head">
                    <span>{title}</span>
                    <button className="x" onClick={onClose}>✕</button>
                </div>
                {children}
            </div>
        </div>
    );
}
