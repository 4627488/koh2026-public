import type { FormEvent } from "react";

import Modal from "./Modal";

type Msg = { ok: boolean; text: string } | null;

type ChangePasswordModalProps = {
    open: boolean;
    onClose: () => void;
    currentPassword: string;
    newPassword: string;
    confirmPassword: string;
    onChangeCurrentPassword: (value: string) => void;
    onChangeNewPassword: (value: string) => void;
    onChangeConfirmPassword: (value: string) => void;
    onSubmit: () => void;
    busy: boolean;
    message: Msg;
};

export default function ChangePasswordModal({
    open,
    onClose,
    currentPassword,
    newPassword,
    confirmPassword,
    onChangeCurrentPassword,
    onChangeNewPassword,
    onChangeConfirmPassword,
    onSubmit,
    busy,
    message,
}: ChangePasswordModalProps) {
    function handleSubmit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        onSubmit();
    }

    return (
        <Modal open={open} onClose={onClose} title="修改密码" position="center">
            <form className="panel" onSubmit={handleSubmit}>
                <div className="fr">
                    <label>当前密码</label>
                    <input
                        type="password"
                        value={currentPassword}
                        onChange={e => onChangeCurrentPassword(e.target.value)}
                        autoFocus
                    />
                </div>
                <div className="fr">
                    <label>新密码</label>
                    <input
                        type="password"
                        value={newPassword}
                        onChange={e => onChangeNewPassword(e.target.value)}
                    />
                </div>
                <div className="fr">
                    <label>确认新密码</label>
                    <input
                        type="password"
                        value={confirmPassword}
                        onChange={e => onChangeConfirmPassword(e.target.value)}
                    />
                </div>
                <div className="dim" style={{ fontSize: 11, marginTop: 8 }}>
                    修改后将使旧登录会话失效，并为当前设备签发新的登录令牌。
                </div>
                <div className="btns" style={{ marginTop: 10 }}>
                    <button type="submit" className="pri" disabled={busy}>
                        {busy ? "提交中…" : "确认修改"}
                    </button>
                    <button type="button" onClick={onClose} disabled={busy}>取消</button>
                </div>
                {message && <div className={`msg ${message.ok ? "ok" : "err"}`}>{message.text}</div>}
            </form>
        </Modal>
    );
}
