import type { SiteConfig, UserProfile } from "@/lib/api";
import Modal from "./Modal";

type HelpModalProps = {
    open: boolean;
    onClose: () => void;
    profile: UserProfile | null;
    siteConfig: SiteConfig | null;
};

function formatTime(iso: string | null | undefined) {
    if (!iso) return "刚刚";
    const d = new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function HelpModal({ open, onClose, profile, siteConfig }: HelpModalProps) {
    const isAdmin = Boolean(profile?.is_admin);
    const announcementTitle = siteConfig?.announcement_title?.trim() || "赛事公告";
    const announcementBody = siteConfig?.announcement_body?.trim() || "暂无公告内容。";
    const announcementLines = announcementBody.split("\n").map(line => line.trim()).filter(Boolean);

    return (
        <Modal open={open} onClose={onClose} title="赛事公告" position="center">
            <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <div
                    style={{
                        border: "1px solid var(--border)",
                        background: "linear-gradient(180deg, #1e2a18 0%, var(--bg3) 100%)",
                        padding: "12px 14px",
                    }}
                >
                    <div className="dim" style={{ fontSize: 11, marginBottom: 6 }}>
                        最新公告 · {formatTime(siteConfig?.announcement_updated_at ?? siteConfig?.updated_at)}
                    </div>
                    <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>{announcementTitle}</div>
                    <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 12, lineHeight: 1.75 }}>
                        {announcementLines.map((line, index) => (
                            <div key={`${index}-${line}`}>{line}</div>
                        ))}
                    </div>
                </div>

                <div style={{ lineHeight: 1.7, fontSize: 12 }}>
                    本赛题为强化学习对抗竞赛（CS 炸弹模式 2v2），选手需训练 AI 模型同时控制己方两名角色，在 25x25 地图上进行攻防对抗。
                </div>
            </div>
            <div className="sh">资源下载</div>
            <div className="panel" style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <a href="/api/artifacts/score_rule.md" download style={{ color: "var(--blue)", textDecoration: "none", fontSize: 12 }}>
                    下载正式赛积分规则（score_rule.md）
                </a>
                <a href="/api/artifacts/KOH_rules.md" download style={{ color: "var(--blue)", textDecoration: "none", fontSize: 12 }}>
                    下载竞赛规则（KOH_rules.md）
                </a>
                <a href="/api/artifacts/koh_env.py" download style={{ color: "var(--blue)", textDecoration: "none", fontSize: 12 }}>
                    下载游戏环境（koh_env.py）
                </a>
                <a href="/api/artifacts/koh_baseline_template.py" download style={{ color: "var(--blue)", textDecoration: "none", fontSize: 12 }}>
                    下载 Baseline 代码（koh_baseline_template.py）
                </a>
            </div>
            <div className="sh">行动建议</div>
            <div className="panel">
                <div style={{ lineHeight: 1.8, fontSize: 12 }}>
                    {!profile
                        ? "建议先完成注册或登录，再根据公告安排准备模型与地图偏好。"
                        : isAdmin
                            ? "建议先在管理面板编辑公告内容，发布后前台会通过 WebSocket 实时接收新公告。"
                            : "建议先保存地图偏好，再分别上传 T 方与 CT 方模型，并关注公告中的赛程与规则变更。"}
                </div>
            </div>
        </Modal>
    );
}
