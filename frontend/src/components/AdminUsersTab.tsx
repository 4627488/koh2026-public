import {
    type AdminRegistrationInvite,
    type AdminUser,
    type ImportUsersResult,
    type SiteConfig,
    type UserProfile,
} from "@/lib/api";
import { fScore, fTime } from "@/lib/format";

type ResetPasswordResult = { username: string; password: string };

interface Props {
    profile: UserProfile;
    siteCfg: SiteConfig | null;
    setSiteCfg: (updater: (prev: SiteConfig | null) => SiteConfig | null) => void;
    adminUsers: AdminUser[];
    adminInvites: AdminRegistrationInvite[];
    showInviteList: boolean;
    setShowInviteList: (updater: (v: boolean) => boolean) => void;
    inviteUses: number;
    setInviteUses: (v: number) => void;
    importText: string;
    setImportText: (v: string) => void;
    importResult: ImportUsersResult | null;
    setImportResult: (v: ImportUsersResult | null) => void;
    importDryRun: boolean;
    setImportDryRun: (v: boolean) => void;
    importBusy: boolean;
    resetPasswordResult: ResetPasswordResult | null;
    setResetPasswordResult: (v: ResetPasswordResult | null) => void;
    onRefresh: () => void;
    onSaveSiteConfig: () => void;
    onCreateInviteLink: () => void;
    onCopyInviteLink: (token: string) => void;
    onRevokeInviteLink: (id: number) => void;
    onImportUsers: () => void;
    onCopyText: (value: string, label: string) => void;
    onToggleActive: (id: number, username: string, isActive: boolean) => void;
    onToggleAdmin: (id: number, username: string, isAdmin: boolean) => void;
    onToggleSpectator: (id: number, username: string, isSpectator: boolean) => void;
    onResetScore: (id: number, username: string) => void;
    onResetPassword: (id: number, username: string) => void;
    onOpenAgentTelemetry: (id: number) => void;
}

export default function AdminUsersTab({
    profile,
    siteCfg,
    setSiteCfg,
    adminUsers,
    adminInvites,
    showInviteList,
    setShowInviteList,
    inviteUses,
    setInviteUses,
    importText,
    setImportText,
    importResult,
    setImportResult,
    importDryRun,
    setImportDryRun,
    importBusy,
    resetPasswordResult,
    setResetPasswordResult,
    onRefresh,
    onSaveSiteConfig,
    onCreateInviteLink,
    onCopyInviteLink,
    onRevokeInviteLink,
    onImportUsers,
    onCopyText,
    onToggleActive,
    onToggleAdmin,
    onToggleSpectator,
    onResetScore,
    onResetPassword,
    onOpenAgentTelemetry,
}: Props) {
    const totalUsers = adminUsers.length;
    const activeUsers = adminUsers.filter(user => user.is_active).length;
    const adminCount = adminUsers.filter(user => user.is_admin).length;
    const spectatorCount = adminUsers.filter(user => user.is_spectator).length;

    return (
        <div className="admin-users-tab">
            <div className="admin-users-toolbar">
                <div className="admin-users-toolbar-actions">
                    <button onClick={onRefresh}>↺ 刷新</button>
                    <button
                        className="pri"
                        onClick={onSaveSiteConfig}
                        disabled={!siteCfg}
                    >
                        保存站点设置
                    </button>
                </div>
                <div className="admin-users-metrics">
                    <div className="admin-users-metric">
                        <span className="dim">总用户</span>
                        <b>{totalUsers}</b>
                    </div>
                    <div className="admin-users-metric">
                        <span className="dim">启用</span>
                        <b style={{ color: "var(--green)" }}>{activeUsers}</b>
                    </div>
                    <div className="admin-users-metric">
                        <span className="dim">管理员</span>
                        <b>{adminCount}</b>
                    </div>
                    <div className="admin-users-metric">
                        <span className="dim">观战</span>
                        <b>{spectatorCount}</b>
                    </div>
                </div>
            </div>

            <div className="admin-users-config-area">
                <div className="admin-users-grid">
                    <section className="panel admin-users-card">
                        <div className="admin-users-card-head">
                            <b>站点设置</b>
                            {siteCfg?.updated_at && (
                                <span className="dim">最近更新 {fTime(siteCfg.updated_at, true)}</span>
                            )}
                        </div>
                        <div className="fr" style={{ marginBottom: 8 }}>
                            <label style={{ minWidth: 84 }}>允许注册</label>
                            <input
                                type="checkbox"
                                checked={Boolean(siteCfg?.allow_registration)}
                                onChange={e => setSiteCfg(prev => prev ? { ...prev, allow_registration: e.target.checked } : prev)}
                                disabled={!siteCfg}
                            />
                            <span className="dim" style={{ fontSize: 11 }}>
                                {siteCfg?.allow_registration ? "新用户可以注册" : "新用户注册已关闭"}
                            </span>
                        </div>
                        <div className="fr" style={{ marginBottom: 0 }}>
                            <label style={{ minWidth: 84 }}>比赛阶段</label>
                            <select
                                value={siteCfg?.phase ?? "competition"}
                                onChange={e => setSiteCfg(prev => prev ? { ...prev, phase: e.target.value } : prev)}
                                disabled={!siteCfg}
                                style={{ background: "var(--bg3)", border: "1px solid var(--border)", color: "var(--fg)", fontFamily: "inherit", fontSize: 12, padding: "2px 6px" }}
                            >
                                <option value="competition">正式赛</option>
                                <option value="test">测试赛</option>
                            </select>
                            <span className="dim" style={{ fontSize: 11 }}>
                                {siteCfg?.phase === "test" ? "测试赛：用户仅可见 Baseline，上传后自动触发测试局" : "正式赛：全员互战，排行榜对所有人可见"}
                            </span>
                        </div>
                    </section>

                    <section className="panel admin-users-card admin-users-card-wide">
                        <div className="admin-users-card-head">
                            <b>公告</b>
                            {siteCfg?.announcement_updated_at && (
                                <span className="dim">最近发布 {fTime(siteCfg.announcement_updated_at, true)}</span>
                            )}
                        </div>
                        <div className="fr" style={{ marginBottom: 8 }}>
                            <label style={{ minWidth: 84 }}>公告标题</label>
                            <input
                                type="text"
                                value={siteCfg?.announcement_title ?? ""}
                                onChange={e => setSiteCfg(prev => prev ? { ...prev, announcement_title: e.target.value } : prev)}
                                disabled={!siteCfg}
                            />
                        </div>
                        <div className="fr" style={{ alignItems: "flex-start", marginBottom: 0 }}>
                            <label style={{ minWidth: 84, marginTop: 4 }}>公告内容</label>
                            <textarea
                                value={siteCfg?.announcement_body ?? ""}
                                onChange={e => setSiteCfg(prev => prev ? { ...prev, announcement_body: e.target.value } : prev)}
                                disabled={!siteCfg}
                                rows={7}
                                style={{
                                    width: "100%",
                                    minHeight: 160,
                                    resize: "vertical",
                                    background: "var(--bg3)",
                                    border: "1px solid var(--border)",
                                    color: "var(--fg)",
                                    fontFamily: "inherit",
                                    fontSize: 12,
                                    lineHeight: 1.6,
                                    padding: "6px 8px",
                                }}
                            />
                        </div>
                        <div className="dim" style={{ fontSize: 11, marginTop: 8, lineHeight: 1.6 }}>
                            每次保存都会更新公告发布时间，并通过 WebSocket 向前台推送最新公告。
                        </div>
                    </section>

                    <section className="panel admin-users-card">
                        <div className="admin-users-card-head">
                            <b>邀请链接</b>
                            <span className="dim">当前共 {adminInvites.length} 条</span>
                        </div>
                        <div className="fr" style={{ marginBottom: 6 }}>
                            <label style={{ minWidth: 84 }}>邀请次数</label>
                            <input
                                type="number"
                                min={1}
                                max={10000}
                                value={inviteUses}
                                onChange={e => setInviteUses(Number(e.target.value) || 1)}
                            />
                            <button className="sm pri" onClick={onCreateInviteLink}>生成链接</button>
                        </div>
                        <div className="dim" style={{ fontSize: 11, marginBottom: 8 }}>
                            1 表示一次性邀请链接；大于 1 表示可重复使用多次。
                        </div>
                        <div className="btns" style={{ marginTop: 0, marginBottom: 8 }}>
                            <button type="button" onClick={() => setShowInviteList(v => !v)}>
                                {showInviteList ? `收起邀请链接 (${adminInvites.length})` : `展开邀请链接 (${adminInvites.length})`}
                            </button>
                        </div>
                        {showInviteList && (
                            <div className="admin-scroll-stack" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                {adminInvites.length === 0
                                    ? <div className="dim" style={{ fontSize: 12 }}>暂无邀请链接</div>
                                    : adminInvites.map(invite => (
                                        <div key={invite.id} className="admin-users-subcard">
                                            <div className="admin-users-subcard-head">
                                                <b>#{invite.id}</b>
                                                <span className="dim">剩余 {invite.remaining_uses}/{invite.max_uses}</span>
                                                <span style={{ color: invite.valid ? "var(--green)" : "var(--red)" }}>
                                                    {invite.revoked ? "已撤销" : invite.valid ? "有效" : "已用尽"}
                                                </span>
                                                <span className="dim" style={{ marginLeft: "auto" }}>
                                                    创建于 {invite.created_at ? fTime(invite.created_at, true) : "—"}
                                                </span>
                                            </div>
                                            <div className="dim" style={{ fontSize: 11, marginTop: 4, wordBreak: "break-all" }}>
                                                {`${window.location.origin}${window.location.pathname}?invite=${encodeURIComponent(invite.token)}`}
                                            </div>
                                            <div className="admin-users-inline-actions">
                                                <button className="sm" onClick={() => onCopyInviteLink(invite.token)}>复制链接</button>
                                                {!invite.revoked && invite.valid && (
                                                    <button className="sm" style={{ color: "var(--red)" }} onClick={() => onRevokeInviteLink(invite.id)}>撤销</button>
                                                )}
                                            </div>
                                        </div>
                                    ))}
                            </div>
                        )}
                    </section>

                    <section className="panel admin-users-card">
                        <div className="admin-users-card-head">
                            <b>批量导入用户</b>
                            <span className="dim">CSV: 显示名, KOH 用户名, KOH 密码</span>
                        </div>
                        <textarea
                            value={importText}
                            onChange={e => { setImportText(e.target.value); setImportResult(null); }}
                            placeholder={"队伍A,user_a,pass123\n队伍B,user_b,pass456"}
                            rows={6}
                            style={{
                                width: "100%",
                                resize: "vertical",
                                background: "var(--bg3)",
                                border: "1px solid var(--border)",
                                color: "var(--fg)",
                                fontFamily: "monospace",
                                fontSize: 12,
                                padding: "6px 8px",
                                boxSizing: "border-box",
                            }}
                        />
                        <div className="admin-users-inline-actions">
                            <label style={{ display: "flex", alignItems: "center", gap: 4, fontSize: 12, cursor: "pointer" }}>
                                <input
                                    type="checkbox"
                                    checked={importDryRun}
                                    onChange={e => { setImportDryRun(e.target.checked); setImportResult(null); }}
                                />
                                预运行（不写入数据库）
                            </label>
                            <button
                                className={importDryRun ? "sm" : "sm pri"}
                                disabled={importBusy || !importText.trim()}
                                onClick={onImportUsers}
                            >
                                {importBusy ? "处理中…" : importDryRun ? "预运行" : "正式导入"}
                            </button>
                        </div>
                        {importResult && (
                            <div style={{ marginTop: 8 }}>
                                <div style={{ display: "flex", gap: 12, fontSize: 12, marginBottom: 6, flexWrap: "wrap" }}>
                                    <span style={{ color: importResult.created_count > 0 ? "var(--green)" : "var(--fg3)" }}>
                                        ✓ 成功 {importResult.created_count} 条{importResult.dry_run ? "（预运行）" : ""}
                                    </span>
                                    {importResult.error_count > 0 && (
                                        <span style={{ color: "var(--red)" }}>✗ 失败 {importResult.error_count} 条</span>
                                    )}
                                    {importResult.blank_lines > 0 && (
                                        <span className="dim">跳过空行 {importResult.blank_lines} 条</span>
                                    )}
                                </div>
                                {importResult.errors.length > 0 && (
                                    <div className="admin-users-result-box">
                                        {importResult.errors.map((err, i) => (
                                            <div key={i} style={{ color: "var(--red)", lineHeight: 1.6 }}>
                                                行 {err.line}{err.username ? ` [${err.username}]` : ""}: {err.error}
                                            </div>
                                        ))}
                                    </div>
                                )}
                                {!importResult.dry_run && importResult.created_count > 0 && (
                                    <div className="admin-users-result-box" style={{ marginTop: 6 }}>
                                        {importResult.created.map((row, i) => (
                                            <div key={i} style={{ lineHeight: 1.6 }}>
                                                <span style={{ color: "var(--green)" }}>✓</span>
                                                {" "}<b>{row.display_name}</b>
                                                <span className="dim"> ({row.username})</span>
                                            </div>
                                        ))}
                                    </div>
                                )}
                            </div>
                        )}
                    </section>

                    {resetPasswordResult && (
                        <section className="panel admin-users-card">
                            <div className="admin-users-card-head">
                                <b>最近一次重置密码</b>
                                <span className="dim">{resetPasswordResult.username}</span>
                            </div>
                            <div style={{ fontSize: 12 }}>
                                <span className="dim">随机密码：</span>
                                <code style={{ color: "var(--blue)", wordBreak: "break-all" }}>{resetPasswordResult.password}</code>
                            </div>
                            <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                                用户旧登录会话已失效，请把这个新密码安全地发给对方。
                            </div>
                            <div className="admin-users-inline-actions">
                                <button
                                    className="sm"
                                    onClick={() => onCopyText(resetPasswordResult.password, "新密码已复制")}
                                >
                                    复制密码
                                </button>
                                <button className="sm" onClick={() => setResetPasswordResult(null)}>清除</button>
                            </div>
                        </section>
                    )}
                </div>
            </div>

            <div className="admin-users-table-section">
                <div className="admin-users-table-head">
                    <b>用户列表</b>
                    <span className="dim">在这里直接管理启用状态、管理员权限、观战权限和密码重置。</span>
                </div>
                <div className="tbl-wrap" style={{ flex: 1 }}>
                    <table>
                        <thead><tr>
                            <th className="r" style={{ width: 40 }}>ID</th>
                            <th>显示名</th>
                            <th>登录账号</th>
                            <th className="r">Score</th>
                            <th style={{ width: 60 }}>管理员</th>
                            <th style={{ width: 60 }}>状态</th>
                            <th style={{ width: 60 }}>观战</th>
                            <th>创建时间</th>
                            <th style={{ width: 220 }}>操作</th>
                        </tr></thead>
                        <tbody>
                            {adminUsers.length === 0
                                ? <tr><td colSpan={9} className="dim" style={{ padding: "8px 10px" }}>暂无用户</td></tr>
                                : adminUsers.map(u => (
                                    <tr key={u.id}>
                                        <td className="r dim">{u.id}</td>
                                        <td style={{ color: u.is_active ? "var(--fg)" : "var(--fg3)" }}>
                                            <b>{u.display_name || u.username}</b>
                                            {u.is_admin && <span className="dim"> ★</span>}
                                            {u.is_spectator && <span className="dim"> 👁</span>}
                                            {u.is_agent && (
                                                <span
                                                    style={{ marginLeft: 4, fontSize: 13, cursor: "pointer" }}
                                                    title={`AI Agent\nagent: ${u.agent_name ?? "?"}\nmodel: ${u.model_name ?? "?"}\n点击查看遥测历史`}
                                                    onClick={() => onOpenAgentTelemetry(u.id)}
                                                >🤖</span>
                                            )}
                                        </td>
                                        <td className="dim" style={{ fontSize: 11 }}>{u.login_username || u.username}</td>
                                        <td className="r">{fScore(u.score)}</td>
                                        <td className="dim">{u.is_admin ? "是" : "—"}</td>
                                        <td style={{ color: u.is_active ? "var(--green)" : "var(--red)" }}>{u.is_active ? "启用" : "停用"}</td>
                                        <td style={{ color: u.is_spectator ? "var(--yellow)" : "var(--fg3)" }}>{u.is_spectator ? "观战" : "—"}</td>
                                        <td className="dim">{fTime(u.created_at)}</td>
                                        <td>
                                            <span className="admin-users-row-actions">
                                                <button
                                                    className="sm"
                                                    style={{ color: u.is_active ? "var(--red)" : "var(--green)" }}
                                                    onClick={() => onToggleActive(u.id, u.username, u.is_active)}
                                                >
                                                    {u.is_active ? "停用" : "启用"}
                                                </button>
                                                <button
                                                    className="sm"
                                                    style={{ color: u.is_admin ? "var(--red)" : "var(--yellow)" }}
                                                    onClick={() => onToggleAdmin(u.id, u.username, u.is_admin)}
                                                >
                                                    {u.is_admin ? "撤销★" : "授予★"}
                                                </button>
                                                <button
                                                    className="sm"
                                                    style={{ color: u.is_spectator ? "var(--green)" : "var(--fg3)" }}
                                                    disabled={u.id === profile.id}
                                                    onClick={() => onToggleSpectator(u.id, u.username, u.is_spectator)}
                                                >
                                                    {u.is_spectator ? "取消观战" : "观战"}
                                                </button>
                                                <button
                                                    className="sm"
                                                    onClick={() => onResetScore(u.id, u.username)}
                                                >
                                                    Score↺
                                                </button>
                                                <button
                                                    className="sm"
                                                    style={{ color: "var(--yellow)" }}
                                                    disabled={u.id === profile.id}
                                                    onClick={() => onResetPassword(u.id, u.username)}
                                                >
                                                    重置密码
                                                </button>
                                            </span>
                                        </td>
                                    </tr>
                                ))
                            }
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    );
}
