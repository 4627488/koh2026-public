import type { InviteStatus } from "@/lib/api";
import Modal from "./Modal";

type Msg = { ok: boolean; text: string } | null;

type RegisterModalProps = {
    open: boolean;
    onClose: () => void;
    username: string;
    password: string;
    onChangeUsername: (value: string) => void;
    onChangePassword: (value: string) => void;
    onSubmit: () => void;
    registerEnabled: boolean;
    inviteToken: string;
    inviteStatus: InviteStatus | null;
    authMsg: Msg;
};

export default function RegisterModal({
    open,
    onClose,
    username,
    password,
    onChangeUsername,
    onChangePassword,
    onSubmit,
    registerEnabled,
    inviteToken,
    inviteStatus,
    authMsg,
}: RegisterModalProps) {
    const hasInvite = inviteToken.trim().length > 0;
    const canRegister = registerEnabled || (hasInvite && Boolean(inviteStatus?.valid));

    return (
        <Modal open={open} onClose={onClose} title="注册" position="center">
            <div className="panel">
                {hasInvite ? (
                    <div className="dim" style={{ fontSize: 12, marginBottom: 8, lineHeight: 1.7 }}>
                        <div>邀请令牌: <span style={{ color: "var(--fg)" }}>{inviteToken}</span></div>
                        <div>
                            状态: {inviteStatus == null ? "加载中…" : inviteStatus.valid ? "有效" : "无效或已用尽"}
                            {inviteStatus && inviteStatus.valid && ` · 剩余 ${inviteStatus.remaining_uses} 次`}
                        </div>
                    </div>
                ) : (
                    <div className="dim" style={{ fontSize: 12, marginBottom: 8 }}>
                        {registerEnabled ? "当前允许公开注册" : "当前仅允许通过邀请链接注册"}
                    </div>
                )}

                <div className="fr">
                    <label>用户</label>
                    <input
                        type="text"
                        value={username}
                        onChange={e => onChangeUsername(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && canRegister && onSubmit()}
                    />
                </div>
                <div className="fr">
                    <label>密码</label>
                    <input
                        type="password"
                        value={password}
                        onChange={e => onChangePassword(e.target.value)}
                        onKeyDown={e => e.key === "Enter" && canRegister && onSubmit()}
                    />
                </div>
                <div className="btns">
                    <button className="pri" onClick={onSubmit} disabled={!canRegister}>注册</button>
                    <button onClick={onClose}>关闭</button>
                </div>
                {!canRegister && (
                    <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                        {!registerEnabled && !hasInvite ? "需要管理员生成邀请链接后才能注册" : "当前邀请链接不可用"}
                    </div>
                )}
                {authMsg && <div className={`msg ${authMsg.ok ? "ok" : "err"}`}>{authMsg.text}</div>}
            </div>
        </Modal>
    );
}
