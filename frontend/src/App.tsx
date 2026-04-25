import { useEffect, useRef, useState } from "react";
import {
    adminCreateMap,
    adminCreateRegistrationInvite,
    adminDeleteMap,
    adminGetAutoRoundConfig,
    adminListMaps,
    adminGetSiteConfig,
    adminCreateRound, adminDeleteRound, adminFinalizeRound,
    adminGetAgentTelemetry, adminGetAllSubmissions, adminGetRoundOverview, adminGetSystem,
    adminListRegistrationInvites,
    adminListBaselines, adminCreateBaseline, adminUpdateBaseline, adminDeleteBaseline, adminListAllSubmissions,
    adminListRounds, adminListUsers, adminPipelineRound, adminRerunRound,
    adminRevokeRegistrationInvite,
    adminResetScore, adminResetFailed, adminResetPassword, adminRetryMatch, adminToggleActive, adminToggleAdmin, adminToggleSpectator,
    adminUpdateMap,
    adminUpdateSiteConfig,
    adminUpdateAutoRoundConfig,
    adminUploadMaps,
    ApiError,
    changePassword,
    connectAnnouncementLive, connectRoundLive, connectTestRunLive, getBp, getScoreHistory, getInviteStatus, getLeaderboard, getMatch,
    getPublicLeaderboard, getPublicScoreHistory,
    downloadRoundMap, downloadTestMap, getMatchReplay, getRegisterStatus, getRoundMaps, getRoundMatches, getRounds, getStatus, getSubmissions, getToken,
    getTestMaps, getTestMatch, getTestMatchReplay, getTestMatches, getTestRunMatches, getTestStatus,
    downloadSubmission, getAllSubmissions,
    login, me, register, setToken, uploadSubmission, upsertBp,
    adminImportUsers,
    type AdminAllSubmission, type AdminBaseline, type AdminMapTemplate, type AdminRegistrationInvite, type AdminRound, type AdminSubmission, type AdminUser, type AutoRoundConfig, type BPData, type ImportUsersResult, type MapUploadResult,
    type ScoreHistoryRow, type LeaderboardRow, type LeaderboardResult, type MatchRow, type RoundLivePayload,
    type ReplayData, type RoundMap, type RoundOverviewUser, type RoundSummary, type ServiceStatus, type TestMatchRow, type TestStatus, type TestRunLivePayload,
    type AgentTelemetryDetail, type InviteStatus, type SiteConfig, type SubmissionRow, type SystemHealth, type UserProfile,
} from "@/lib/api";
import ChangePasswordModal from "./components/ChangePasswordModal";
import AdminUsersTab from "./components/AdminUsersTab";
import HelpModal from "./components/HelpModal";
import GridCanvas from "./components/GridCanvas";
import MapEditorModal from "./components/MapEditorModal";
import MatchesTable from "./components/MatchesTable";
import Modal from "./components/Modal";
import RegisterModal from "./components/RegisterModal";
import ReplayModal from "./components/ReplayModal";

/* ── helpers ─────────────────────────────────────────────────── */
const DEFAULT_ROUND = 1;

const fTime = (iso: string, sec = false) => {
    const d = new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
    const pad = (n: number) => String(n).padStart(2, "0");
    const base = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    return sec ? base + `:${pad(d.getSeconds())}` : base;
};
const toDatetimeLocalValue = (iso: string | null | undefined) => {
    if (!iso) return "";
    const d = new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
    const pad = (n: number) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
};
const fromDatetimeLocalValue = (value: string) => value ? new Date(value).toISOString() : null;
const fScore = (v: number) => v.toFixed(4);
const fRate = (v: number) => (v * 100).toFixed(1);
const fDelta = (v: number) => { const s = Math.abs(v).toFixed(4); return v >= 0 ? `+${s}` : `-${s}`; };
const fDeltaClass = (v: number) => v > 0.05 ? "elo-up" : v < -0.05 ? "elo-down" : "elo-flat";
const zhRole = (role: string) => role === "attack" ? "T方" : role === "defense" ? "CT方" : role;
const zhWinner = (w: string) => w === "attacker" ? "T方胜" : w === "defender" ? "CT方胜" : w === "draw" ? "平局" : w;
const zhOutcome = (outcome: string) => outcome === "win" ? "胜利" : outcome === "loss" ? "失败" : outcome === "draw" ? "平局" : outcome;
const zhReason = (r: string) => {
    const map: Record<string, string> = {
        bomb_exploded: "炸弹爆炸",
        bomb_defused: "炸弹拆除",
        all_t_dead: "T方全灭",
        all_ct_dead: "CT方全灭",
        timeout: "超时（炸弹未安放）",
        in_progress: "进行中",
    };
    return map[r] ?? r;
};
const zhStatus = (status: string) => {
    if (status === "queued") return "排队";
    if (status === "running" || status === "strategy_window") return "进行中";
    if (status === "completed") return "已完成";
    if (status === "failed") return "失败";
    return status;
};
const zhScheduleState = (state: string) => {
    const map: Record<string, string> = {
        disabled: "未启用",
        unscheduled: "未设置赛程",
        invalid: "赛程配置无效",
        before_start: "未开始",
        running: "进行中",
        finished: "已结束",
    };
    return map[state] ?? state;
};
const mapDownloadFilename = (map: Pick<AdminMapTemplate, "name" | "slug">) => {
    const base = (map.slug || map.name || "map")
        .trim()
        .replace(/[\\/:*?"<>|]+/g, "-")
        .replace(/\s+/g, "-");
    return `${base || "map"}.txt`;
};
const fRemain = (targetIso: string) => {
    const target = new Date(/[Z+]/.test(targetIso) ? targetIso : targetIso + "Z");
    const sec = Math.max(0, Math.floor((target.getTime() - Date.now()) / 1000));
    const hh = Math.floor(sec / 3600);
    const mm = Math.floor((sec % 3600) / 60);
    const ss = sec % 60;
    if (hh > 0) return `${hh}h${String(mm).padStart(2, "0")}m`;
    if (mm > 0) return `${mm}m${String(ss).padStart(2, "0")}s`;
    return `${ss}s`;
};
const zhReplayPhase = (phase: string) => {
    if (phase === "start") return "起始";
    if (phase === "end") return "结束";
    return "进行中";
};

const actionLabel = (a: number) => {
    const map: Record<number, string> = {
        0: "↑",
        1: "↓",
        2: "←",
        3: "→",
        4: "·",
        5: "开火↑",
        6: "开火↓",
        7: "开火←",
        8: "开火→",
    };
    return map[a] ?? String(a);
};

const actionPairLabel = (pair: [number, number] | null) =>
    pair ? `${actionLabel(pair[0])}, ${actionLabel(pair[1])}` : "—";

const modelIdLabel = (v: string | null | undefined) => (v ? `#${v.slice(0, 8)}` : "—");
const helpSeenKey = (userId: number, version: string) => `koh_help_seen_user_${userId}_${version}`;

type Msg = { ok: boolean; text: string } | null;
type MatchViewMode = "global" | "self";
type Selected = { kind: "match"; id: number } | { kind: "user"; username: string } | { kind: "map"; id: number } | null;
type ResetPasswordResult = { username: string; password: string } | null;

function PublicLeaderboardPage() {
    const [board, setBoard] = useState<LeaderboardRow[]>([]);
    const [phase, setPhase] = useState("competition");
    const [svcStatus, setSvcStatus] = useState<ServiceStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [selectedUser, setSelectedUser] = useState<string | null>(null);
    const [scoreHistory, setScoreHistory] = useState<ScoreHistoryRow[]>([]);
    const [detailBusy, setDetailBusy] = useState(false);

    useEffect(() => {
        let cancelled = false;

        Promise.all([
            getPublicLeaderboard(),
            getStatus().catch(() => null),
        ])
            .then(([lb, status]) => {
                if (cancelled) return;
                setBoard(lb.rows);
                setPhase(lb.phase);
                setSvcStatus(status);
                setError(null);
            })
            .catch((err: unknown) => {
                if (cancelled) return;
                setError(err instanceof Error ? err.message : "外榜加载失败");
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });

        return () => {
            cancelled = true;
        };
    }, []);

    useEffect(() => {
        if (!selectedUser) {
            setScoreHistory([]);
            return;
        }
        let cancelled = false;
        setDetailBusy(true);
        getPublicScoreHistory(selectedUser)
            .then(rows => {
                if (cancelled) return;
                setScoreHistory(rows);
            })
            .catch(() => {
                if (cancelled) return;
                setScoreHistory([]);
            })
            .finally(() => {
                if (!cancelled) setDetailBusy(false);
            });
        return () => {
            cancelled = true;
        };
    }, [selectedUser]);

    return (
        <div className="app" style={{ minHeight: "100vh", padding: "24px 16px", alignItems: "flex-start" }}>
            <div className="main" style={{ maxWidth: 1240, margin: "0 auto", width: "100%" }}>
                <div className="panel" style={{ marginBottom: 12 }}>
                    <div className="sh" style={{ marginBottom: 12 }}>Asuri Major · 外榜</div>
                    <div className="dim" style={{ fontSize: 12 }}>
                        {svcStatus?.phase === "competition" && svcStatus?.current_round_id != null
                            ? `当前第 ${svcStatus.current_round_id} 轮 · 点击行 → 积分历史`
                            : phase === "test"
                                ? "当前处于测试阶段，公开外榜暂不展示测试榜数据"
                                : "点击行 → 积分历史"}
                    </div>
                </div>

                {loading && <div className="panel dim">加载中…</div>}
                {!loading && error && <div className="panel msg err">{error}</div>}
                {!loading && !error && (
                    <div style={{ display: "grid", gridTemplateColumns: selectedUser ? "minmax(0, 1fr) 320px" : "minmax(0, 1fr)", gap: 12, alignItems: "start" }}>
                        <div className="game-board-section panel">
                            <div className="sh">
                                排行榜
                                <span style={{ float: "right", fontWeight: "normal", textTransform: "none", letterSpacing: 0 }} className="dim">
                                    {phase === "test" ? "测试阶段不显示正式排行榜" : "点击行 → 积分历史"}
                                </span>
                            </div>
                            <div className="tbl-wrap">
                                <table>
                                    <thead><tr>
                                        <th style={{ width: 28 }}>#</th>
                                        <th>用户</th>
                                        <th className="r">score</th>
                                        <th className="r">胜</th>
                                        <th className="r">平</th>
                                        <th className="r">负</th>
                                        <th className="r">进攻%</th>
                                        <th className="r">防守%</th>
                                        <th className="r">Δscore</th>
                                    </tr></thead>
                                    <tbody>
                                        {board.length === 0
                                            ? <tr><td colSpan={9} className="dim" style={{ padding: "6px 8px" }}>
                                                {phase === "test" ? "测试阶段不展示公开外榜" : "暂无数据"}
                                            </td></tr>
                                            : board.map((row, i) => {
                                                const isSel = selectedUser === row.username;
                                                return (
                                                    <tr
                                                        key={row.username}
                                                        className={`click${isSel ? " sel" : ""}`}
                                                        onClick={() => setSelectedUser(isSel ? null : row.username)}
                                                    >
                                                        <td className="r dim">{i + 1}</td>
                                                        <td className="uname">{row.username}{row.is_agent && <span style={{ marginLeft: 4, fontSize: 12 }} title="AI Agent">🤖</span>}</td>
                                                        <td className="r">{fScore(row.score)}</td>
                                                        <td className="r pos">{row.wins}</td>
                                                        <td className="r dim">{row.draws}</td>
                                                        <td className="r neg">{row.losses}</td>
                                                        <td className="r">{fRate(row.attack_win_rate)}</td>
                                                        <td className="r">{fRate(row.defense_win_rate)}</td>
                                                        <td className={`r ${row.score_delta >= 0 ? "pos" : "neg"}`}>{fDelta(row.score_delta)}</td>
                                                    </tr>
                                                );
                                            })}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        {selectedUser && (
                            <div className="detail" style={{ width: 320, minWidth: 320, position: "sticky", top: 24 }}>
                                <div className="detail-head">
                                    <><span>用户 </span><b>{selectedUser}</b></>
                                    <button className="x" onClick={() => setSelectedUser(null)}>✕</button>
                                </div>
                                {detailBusy && <div className="dim" style={{ padding: "8px 10px", fontSize: 11 }}>加载中…</div>}
                                {!detailBusy && (
                                    <>
                                        <div className="sh">积分历史 — {selectedUser}</div>
                                        <table>
                                            <thead><tr>
                                                <th className="r">轮次</th>
                                                <th className="r">前值</th>
                                                <th className="r">后值</th>
                                                <th className="r">Δ</th>
                                            </tr></thead>
                                            <tbody>
                                                {scoreHistory.length === 0
                                                    ? <tr><td colSpan={4} className="dim" style={{ padding: "6px 8px" }}>暂无历史</td></tr>
                                                    : scoreHistory.map((h) => (
                                                        <tr key={h.round_id}>
                                                            <td className="r dim">{h.round_id}</td>
                                                            <td className="r">{fScore(h.score_before)}</td>
                                                            <td className="r">{fScore(h.score_after)}</td>
                                                            <td className={`r ${fDeltaClass(h.delta)}`}>{fDelta(h.delta)}</td>
                                                        </tr>
                                                    ))}
                                            </tbody>
                                        </table>
                                    </>
                                )}
                            </div>
                        )}
                    </div>
                )}

                <div className="dim" style={{ marginTop: 14, fontSize: 12 }}>
                    <a href="/" style={{ color: "var(--blue)", textDecoration: "underline" }}>返回主页</a>
                </div>
            </div>
        </div>
    );
}

/* ══════════════════════════════════════════════════════════════ */
export default function App() {
    function clearInviteFromUrl() {
        const url = new URL(window.location.href);
        url.searchParams.delete("invite");
        window.history.replaceState({}, "", url.toString());
    }

    if (window.location.pathname === "/leaderboard") {
        return <PublicLeaderboardPage />;
    }

    /* core data */
    const [profile, setProfile] = useState<UserProfile | null>(null);
    const [board, setBoard] = useState<LeaderboardRow[]>([]);
    const [leaderboardPhase, setLeaderboardPhase] = useState<string>("competition");
    const [maps, setMaps] = useState<RoundMap[]>([]);
    const [matches, setMatches] = useState<MatchRow[]>([]);
    const [live, setLive] = useState<RoundLivePayload | null>(null);
    const [svcStatus, setSvcStatus] = useState<ServiceStatus | null>(null);
    const [testStatus, setTestStatus] = useState<TestStatus | null>(null);
    const [testLive, setTestLive] = useState<TestRunLivePayload | null>(null);
    const [roundId, setRoundId] = useState(DEFAULT_ROUND);
    const [rounds, setRounds] = useState<RoundSummary[]>([]);
    const [nowTick, setNowTick] = useState(Date.now());

    /* forms */
    const [lUser, setLUser] = useState("");
    const [lPass, setLPass] = useState("");
    const [rUser, setRUser] = useState("");
    const [rPass, setRPass] = useState("");
    const [registerOpen, setRegisterOpen] = useState(false);
    const [registerInviteToken, setRegisterInviteToken] = useState("");
    const [mapPreferences, setMapPreferences] = useState<number[]>([]);
    const [authMsg, setAuthMsg] = useState<Msg>(null);
    const [accountMsg, setAccountMsg] = useState<Msg>(null);
    const [bpMsg, setBpMsg] = useState<Msg>(null);
    const [registerStatus, setRegisterStatus] = useState<SiteConfig | null>(null);
    const [inviteStatus, setInviteStatus] = useState<InviteStatus | null>(null);
    const [changePasswordOpen, setChangePasswordOpen] = useState(false);
    const [currentPassword, setCurrentPassword] = useState("");
    const [newPassword, setNewPassword] = useState("");
    const [confirmPassword, setConfirmPassword] = useState("");
    const [changePasswordBusy, setChangePasswordBusy] = useState(false);
    const [changePasswordMsg, setChangePasswordMsg] = useState<Msg>(null);

    /* detail pane */
    const [selected, setSelected] = useState<Selected>(null);
    const [matchDetail, setMatchDetail] = useState<MatchRow | TestMatchRow | null>(null);
    const [replayData, setReplayData] = useState<ReplayData | null>(null);
    const [replayBusy, setReplayBusy] = useState(false);
    const [replayError, setReplayError] = useState<string | null>(null);
    const [replayFrameIndex, setReplayFrameIndex] = useState(0);
    const [replayPlaying, setReplayPlaying] = useState(false);
    const [replaySpeedMs, setReplaySpeedMs] = useState(500);
    const [replayOpen, setReplayOpen] = useState(false);
    const [scoreHistory, setScoreHistory] = useState<ScoreHistoryRow[]>([]);
    const [detailBusy, setDetailBusy] = useState(false);

    /* submissions */
    const [subRole, setSubRole] = useState<"attack" | "defense">("attack");
    const [subFile, setSubFile] = useState<File | null>(null);
    const [subList, setSubList] = useState<SubmissionRow[]>([]);
    const [subHistory, setSubHistory] = useState<SubmissionRow[]>([]);
    const [subHistoryOpen, setSubHistoryOpen] = useState(false);
    const [subMsg, setSubMsg] = useState<Msg>(null);
    const [subBusy, setSubBusy] = useState(false);
    const [helpOpen, setHelpOpen] = useState(false);

    /* layout */
    const [sidebarWidth, setSidebarWidth] = useState(210);
    const [detailWidth, setDetailWidth] = useState(290);

    /* view */
    const [view, setView] = useState<"game" | "admin">("game");
    const [matchView, setMatchView] = useState<MatchViewMode>("global");

    /* admin */
    const [adminTab, setAdminTab] = useState<"rounds" | "baselines" | "maps" | "users" | "health" | "overview" | "subs" | "auto">("rounds");
    const [adminRounds, setAdminRounds] = useState<AdminRound[]>([]);
    const [adminMaps, setAdminMaps] = useState<AdminMapTemplate[]>([]);
    const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
    const [adminBaselines, setAdminBaselines] = useState<AdminBaseline[]>([]);
    const [adminAllSubs, setAdminAllSubs] = useState<AdminSubmission[]>([]);
    const [baselinesBusy, setBaselinesBusy] = useState(false);
    // create-baseline form
    const [blName, setBlName] = useState("");
    const [blAtkId, setBlAtkId] = useState<number | "">("");
    const [blDefId, setBlDefId] = useState<number | "">("");
    const [blSortOrder, setBlSortOrder] = useState(0);
    const [blAtkSearch, setBlAtkSearch] = useState("");
    const [blDefSearch, setBlDefSearch] = useState("");
    // edit-baseline state
    const [editingBaseline, setEditingBaseline] = useState<AdminBaseline | null>(null);
    const [adminMsg, setAdminMsg] = useState<Msg>(null);
    const [sysHealth, setSysHealth] = useState<SystemHealth | null>(null);
    const [sysHealthBusy, setSysHealthBusy] = useState(false);
    const [roundOverview, setRoundOverview] = useState<RoundOverviewUser[]>([]);
    const [allSubs, setAllSubs] = useState<AdminAllSubmission[]>([]);
    const [autoRoundCfg, setAutoRoundCfg] = useState<AutoRoundConfig | null>(null);
    const [siteCfg, setSiteCfg] = useState<SiteConfig | null>(null);
    const [adminInvites, setAdminInvites] = useState<AdminRegistrationInvite[]>([]);
    const [showInviteList, setShowInviteList] = useState(false);
    const [resetPasswordResult, setResetPasswordResult] = useState<ResetPasswordResult>(null);
    const [agentTelemetryOpen, setAgentTelemetryOpen] = useState(false);
    const [agentTelemetryDetail, setAgentTelemetryDetail] = useState<AgentTelemetryDetail | null>(null);
    const [agentTelemetryBusy, setAgentTelemetryBusy] = useState(false);
    const [inviteUses, setInviteUses] = useState(1);
    const [autoRoundBusy, setAutoRoundBusy] = useState(false);
    const [mapEditorOpen, setMapEditorOpen] = useState(false);
    const [editingMap, setEditingMap] = useState<AdminMapTemplate | null>(null);
    const [mapSaveBusy, setMapSaveBusy] = useState(false);
    const [mapSaveMsg, setMapSaveMsg] = useState<string | null>(null);
    const [mapUploadBusy, setMapUploadBusy] = useState(false);
    const [mapUploadMsg, setMapUploadMsg] = useState<string | null>(null);
    const mapUploadRef = useRef<HTMLInputElement>(null);
    const [importText, setImportText] = useState("");
    const [importDryRun, setImportDryRun] = useState(true);
    const [importBusy, setImportBusy] = useState(false);
    const [importResult, setImportResult] = useState<ImportUsersResult | null>(null);

    /* track profile id to avoid spurious BP reloads */
    const profileId = useRef<number | null>(null);
    const reloadTimerRef = useRef<number | null>(null);
    const reloadInFlightRef = useRef(false);
    const reloadQueuedRef = useRef(false);
    const selectedMatchId = selected?.kind === "match" ? selected.id : null;
    const currentUserId = profile?.id ?? null;
    const profileName = profile?.display_name || profile?.username || "";
    const forceGlobalMatchView = svcStatus?.phase === "test" && Boolean(profile?.is_admin);
    const ownMatches = currentUserId == null
        ? []
        : matches.filter(row => row.team_a_id === currentUserId || row.team_b_id === currentUserId);
    const effectiveMatchView: MatchViewMode = forceGlobalMatchView ? "global" : matchView;
    const visibleMatches = effectiveMatchView === "self" && currentUserId != null ? ownMatches : matches;
    const selectedMatchVisible = selectedMatchId == null
        ? true
        : visibleMatches.some(row => row.id === selectedMatchId);

    /* ── data loading ───────────────────────────────────────── */
    async function reload() {
        if (svcStatus?.phase === "test") {
            const [ts, tm, tr, lb] = await Promise.all([
                getTestStatus().catch((): TestStatus => ({ phase: "test", has_bundle: false, latest_bundle: null, latest_run: null })),
                getTestMaps().catch((): RoundMap[] => []),
                profile?.is_admin
                    ? getTestMatches(500).then(rows => rows as unknown as MatchRow[]).catch((): MatchRow[] => [])
                    : getTestStatus().then(async status => {
                        if (!status.latest_run) return [] as MatchRow[];
                        return getTestRunMatches(status.latest_run.id).then(rows => rows as unknown as MatchRow[]);
                    }).catch((): MatchRow[] => []),
                profile?.is_admin
                    ? getLeaderboard().catch((): LeaderboardResult => ({ rows: [], phase: "test" }))
                    : Promise.resolve({ rows: [], phase: "test" } as LeaderboardResult),
            ]);
            setTestStatus(ts);
            setBoard(lb.rows);
            setLeaderboardPhase(lb.phase);
            setMaps(tm);
            setMatches(tr);
            setRounds([]);
            return;
        }
        const [lb, m, mx, rs] = await Promise.all([
            getLeaderboard().catch((): LeaderboardResult => ({ rows: [], phase: "competition" })),
            getRoundMaps(roundId).catch((): RoundMap[] => []),
            getRoundMatches(roundId).catch((): MatchRow[] => []),
            getRounds(80).catch((): RoundSummary[] => []),
        ]);
        setBoard(lb.rows);
        setLeaderboardPhase(lb.phase);
        setMaps(m);
        setMatches(mx);
        setRounds(rs);
    }

    function scheduleReload(delayMs = 300) {
        if (reloadTimerRef.current != null) {
            window.clearTimeout(reloadTimerRef.current);
        }
        reloadTimerRef.current = window.setTimeout(() => {
            reloadTimerRef.current = null;
            if (reloadInFlightRef.current) {
                reloadQueuedRef.current = true;
                return;
            }

            reloadInFlightRef.current = true;
            void reload()
                .catch(() => { })
                .finally(() => {
                    reloadInFlightRef.current = false;
                    if (reloadQueuedRef.current) {
                        reloadQueuedRef.current = false;
                        scheduleReload(150);
                    }
                });
        }, delayMs);
    }

    function changeMatchView(next: MatchViewMode) {
        if (forceGlobalMatchView) {
            setMatchView("global");
            return;
        }
        if (next === "self" && currentUserId == null) return;
        setMatchView(next);
        if (selectedMatchId != null && next === "self" && !ownMatches.some(row => row.id === selectedMatchId)) {
            setSelected(null);
        }
    }

    function applyBp(data: BPData) {
        if (!data) return;
        setMapPreferences(data.map_preferences ?? []);
    }

    async function loadBp(_rid?: number) {
        getBp().then(applyBp).catch(() => { });
    }

    /* ── effects ────────────────────────────────────────────── */
    useEffect(() => {
        const invite = new URLSearchParams(window.location.search).get("invite")?.trim() ?? "";
        if (invite) {
            setRegisterInviteToken(invite);
            setRegisterOpen(true);
            getInviteStatus(invite).then(setInviteStatus).catch(() => { });
        }
        getStatus().then(s => {
            setSvcStatus(s);
            const preferredRoundId = s.current_round_id
                ?? (s.auto_round_state === "before_start" ? s.next_round_id : null);
            if (preferredRoundId != null) setRoundId(preferredRoundId);
        }).catch(() => { });
        getRegisterStatus().then(setRegisterStatus).catch(() => { });
        if (getToken()) {
            me()
                .then(p => {
                    setProfile(p);
                    profileId.current = p.id;
                })
                .catch((error: unknown) => {
                    if (error instanceof ApiError && error.status === 401) {
                        setToken("");
                        setProfile(null);
                        profileId.current = null;
                        return;
                    }
                    console.warn("initial auth refresh failed without 401; keeping token", error);
                });
        }
    }, []);

    useEffect(() => {
        const ws = connectAnnouncementLive((cfg) => {
            setRegisterStatus(cfg);
        });
        return () => ws.close();
    }, []);

    useEffect(() => { void reload(); }, [roundId, svcStatus?.phase, profile?.is_admin]);

    useEffect(() => () => {
        if (reloadTimerRef.current != null) {
            window.clearTimeout(reloadTimerRef.current);
        }
    }, []);

    useEffect(() => {
        if (profile) void loadBp(roundId);
    }, [profile, roundId, svcStatus?.phase]);

    useEffect(() => {
        if (!profile || profile.is_admin || !registerStatus) return;
        const version = registerStatus.announcement_updated_at ?? registerStatus.updated_at;
        const key = helpSeenKey(profile.id, version || "default");
        if (localStorage.getItem(key) === "1") return;
        setHelpOpen(true);
        localStorage.setItem(key, "1");
    }, [profile, registerStatus]);

    useEffect(() => {
        if (profile) {
            void getSubmissions(roundId).then(setSubList).catch(() => { });
            void getAllSubmissions().then(setSubHistory).catch(() => { });
        }
    }, [profile, roundId, svcStatus?.phase]);

    useEffect(() => {
        if (profile?.is_admin) {
            void loadAdminData();
            void loadAdminMaps();
            void loadAutoRoundConfig();
            void loadSiteConfig();
            void loadRegistrationInvites();
        }
    }, [profile]);

    useEffect(() => {
        const token = registerInviteToken.trim();
        if (!token) {
            setInviteStatus(null);
            return;
        }
        getInviteStatus(token).then(setInviteStatus).catch(() => setInviteStatus(null));
    }, [registerInviteToken]);

    useEffect(() => {
        if (matchView === "self" && currentUserId == null) {
            setMatchView("global");
        }
    }, [currentUserId, matchView]);

    useEffect(() => {
        if (forceGlobalMatchView && matchView !== "global") {
            setMatchView("global");
        }
    }, [forceGlobalMatchView, matchView]);

    useEffect(() => {
        const timer = window.setInterval(() => setNowTick(Date.now()), 1000);
        return () => window.clearInterval(timer);
    }, []);

    useEffect(() => {
        if (!selectedMatchVisible) {
            setSelected(null);
        }
    }, [selectedMatchVisible]);

    useEffect(() => {
        setLive(null);
        setTestLive(null);
        if (svcStatus?.phase === "test") {
            if (!testStatus?.latest_run) return;
            const ws = connectTestRunLive(testStatus.latest_run.id, (p) => {
                setTestLive(p);
                scheduleReload();
            });
            return () => ws.close();
        }
        const ws = connectRoundLive(roundId, (p) => {
            setLive(p);
            scheduleReload();
        });
        return () => ws.close();
    }, [roundId, svcStatus?.phase, testStatus?.latest_run?.id]);

    useEffect(() => {
        if (!selected) {
            setMatchDetail(null);
            setReplayData(null);
            setReplayError(null);
            setReplayBusy(false);
            setReplayFrameIndex(0);
            setReplayPlaying(false);
            setReplayOpen(false);
            setScoreHistory([]);
            return;
        }
        setDetailBusy(true);
        if (selected.kind === "match") {
            const loader = svcStatus?.phase === "test" ? getTestMatch(selected.id) : getMatch(selected.id);
            loader
                .then(setMatchDetail)
                .catch(() => setMatchDetail(null))
                .finally(() => setDetailBusy(false));
        } else if (selected.kind === "user") {
            getScoreHistory(selected.username)
                .then(setScoreHistory)
                .catch(() => setScoreHistory([]))
                .finally(() => setDetailBusy(false));
        } else {
            // map — data already in state, no fetch needed
            setDetailBusy(false);
        }
    }, [selected, svcStatus?.phase]);

    useEffect(() => {
        if (selectedMatchId == null || matchDetail?.status !== "completed") {
            setReplayData(null);
            setReplayError(null);
            setReplayBusy(false);
            setReplayFrameIndex(0);
            setReplayPlaying(false);
            setReplayOpen(false);
            return;
        }

        let cancelled = false;
        setReplayBusy(true);
        setReplayError(null);
        setReplayPlaying(false);
        setReplayFrameIndex(0);

        const loader = svcStatus?.phase === "test" ? getTestMatchReplay(selectedMatchId) : getMatchReplay(selectedMatchId);
        loader
            .then(data => {
                if (cancelled) return;
                setReplayData(data);
                setReplayFrameIndex(0);
            })
            .catch(err => {
                if (cancelled) return;
                setReplayData(null);
                setReplayError(err instanceof Error ? err.message : "回放加载失败");
            })
            .finally(() => {
                if (!cancelled) setReplayBusy(false);
            });

        return () => {
            cancelled = true;
        };
    }, [selectedMatchId, matchDetail?.status, svcStatus?.phase]);

    useEffect(() => {
        if (!replayPlaying || !replayData?.frames.length) return;
        const timer = window.setInterval(() => {
            setReplayFrameIndex(current => {
                const next = current + 1;
                if (next >= replayData.frames.length) {
                    window.clearInterval(timer);
                    setReplayPlaying(false);
                    return current;
                }
                return next;
            });
        }, replaySpeedMs);
        return () => window.clearInterval(timer);
    }, [replayPlaying, replayData, replaySpeedMs]);

    /* ── actions ────────────────────────────────────────────── */
    async function doLogin() {
        const trimmedUser = lUser.trim();
        const trimmedPass = lPass.trim();

        if (!trimmedUser || !trimmedPass) {
            setAuthMsg({ ok: false, text: "用户名和密码不能为空" });
            return;
        }

        try {
            const d = await login(trimmedUser, trimmedPass);
            setToken(d.token);
            const u = await me();
            setProfile(u);
            profileId.current = u.id;
            setAuthMsg({ ok: true, text: `登录成功: ${u.display_name || u.username}` });
        } catch (e) {
            setAuthMsg({ ok: false, text: e instanceof Error ? e.message : "登录失败" });
        }
    }

    async function doRegister() {
        const trimmedUser = rUser.trim();
        const trimmedPass = rPass.trim();

        if (!trimmedUser || !trimmedPass) {
            setAuthMsg({ ok: false, text: "用户名和密码不能为空" });
            return;
        }

        try {
            const d = await register(trimmedUser, trimmedPass, registerInviteToken.trim() || undefined);
            setAuthMsg({ ok: true, text: `注册成功: ${d.username}` });
            setRegisterOpen(false);
            setRPass("");
            void getRegisterStatus().then(setRegisterStatus).catch(() => { });
            if (registerInviteToken.trim()) {
                void getInviteStatus(registerInviteToken.trim()).then(setInviteStatus).catch(() => { });
                clearInviteFromUrl();
                setRegisterInviteToken("");
            }
        } catch (e) {
            setAuthMsg({ ok: false, text: e instanceof Error ? e.message : "注册失败" });
            void getRegisterStatus().then(setRegisterStatus).catch(() => { });
            if (registerInviteToken.trim()) {
                void getInviteStatus(registerInviteToken.trim()).then(setInviteStatus).catch(() => { });
            }
        }
    }

    function openChangePasswordModal() {
        setCurrentPassword("");
        setNewPassword("");
        setConfirmPassword("");
        setChangePasswordMsg(null);
        setChangePasswordOpen(true);
    }

    async function doChangePassword() {
        if (!currentPassword.trim() || !newPassword.trim() || !confirmPassword.trim()) {
            setChangePasswordMsg({ ok: false, text: "请填写完整的密码信息" });
            return;
        }
        if (newPassword !== confirmPassword) {
            setChangePasswordMsg({ ok: false, text: "两次输入的新密码不一致" });
            return;
        }

        setChangePasswordBusy(true);
        setChangePasswordMsg(null);
        try {
            const data = await changePassword(currentPassword, newPassword);
            setToken(data.token);
            const u = await me();
            setProfile(u);
            profileId.current = u.id;
            setAccountMsg({ ok: true, text: "密码已更新" });
            setChangePasswordOpen(false);
            setCurrentPassword("");
            setNewPassword("");
            setConfirmPassword("");
        } catch (e) {
            setChangePasswordMsg({ ok: false, text: e instanceof Error ? e.message : "修改密码失败" });
        } finally {
            setChangePasswordBusy(false);
        }
    }

    async function saveBp() {
        try {
            await upsertBp({ map_preferences: mapPreferences });
            setBpMsg({ ok: true, text: "已保存" });
        } catch (e) {
            setBpMsg({ ok: false, text: e instanceof Error ? e.message : "保存失败" });
        }
    }

    function toggleMapPreference(mapIdx: number) {
        setMapPreferences(prev => {
            if (prev.includes(mapIdx)) return prev.filter(i => i !== mapIdx);
            return [...prev, mapIdx];
        });
    }

    function moveMapPreference(mapIdx: number, dir: -1 | 1) {
        setMapPreferences(prev => {
            const idx = prev.indexOf(mapIdx);
            if (idx === -1) return prev;
            const next = idx + dir;
            if (next < 0 || next >= prev.length) return prev;
            const arr = [...prev];
            [arr[idx], arr[next]] = [arr[next], arr[idx]];
            return arr;
        });
    }

    async function doUpload() {
        if (!subFile) { setSubMsg({ ok: false, text: "请先选择文件" }); return; }
        setSubBusy(true);
        setSubMsg(null);
        try {
            const res = await uploadSubmission(subRole, subFile);
            const modelId = res.id;
            setSubMsg({ ok: true, text: `上传成功: ${res.role} ${modelIdLabel(modelId)}` });
            setSubFile(null);
            void getSubmissions(roundId).then(setSubList).catch(() => { });
            void getAllSubmissions().then(setSubHistory).catch(() => { });
            void reload();
        } catch (e) {
            setSubMsg({ ok: false, text: e instanceof Error ? e.message : "上传失败" });
        } finally {
            setSubBusy(false);
        }
    }

    async function loadAdminData() {
        try {
            const [rounds, users] = await Promise.all([adminListRounds(), adminListUsers()]);
            setAdminRounds(rounds);
            setAdminUsers(users);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "加载失败" });
        }
    }

    async function loadAdminMaps() {
        try {
            const rows = await adminListMaps();
            setAdminMaps(rows);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "地图加载失败" });
        }
    }

    async function loadBaselines() {
        setBaselinesBusy(true);
        try {
            const [bls, subs] = await Promise.all([adminListBaselines(), adminListAllSubmissions()]);
            setAdminBaselines(bls);
            setAdminAllSubs(subs);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "baseline 加载失败" });
        } finally {
            setBaselinesBusy(false);
        }
    }

    async function createBaseline() {
        if (!blName.trim()) { setAdminMsg({ ok: false, text: "请填写显示名" }); return; }
        if (blAtkId === "" || blDefId === "") { setAdminMsg({ ok: false, text: "请选择攻击和防守提交" }); return; }
        setBaselinesBusy(true);
        try {
            await adminCreateBaseline({
                display_name: blName.trim(),
                attack_submission_id: Number(blAtkId),
                defense_submission_id: Number(blDefId),
                sort_order: blSortOrder,
                is_active: true,
            });
            setAdminMsg({ ok: true, text: `Baseline「${blName.trim()}」已创建` });
            setBlName(""); setBlAtkId(""); setBlDefId(""); setBlSortOrder(0);
            setBlAtkSearch(""); setBlDefSearch("");
            void loadBaselines();
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "创建失败" });
        } finally {
            setBaselinesBusy(false);
        }
    }

    async function saveEditingBaseline() {
        if (!editingBaseline) return;
        if (!editingBaseline.display_name.trim()) { setAdminMsg({ ok: false, text: "显示名不能为空" }); return; }
        setBaselinesBusy(true);
        try {
            await adminUpdateBaseline(editingBaseline.id, {
                display_name: editingBaseline.display_name.trim(),
                sort_order: editingBaseline.sort_order,
                is_active: editingBaseline.is_active,
            });
            setAdminMsg({ ok: true, text: `Baseline #${editingBaseline.id} 已更新` });
            setEditingBaseline(null);
            void loadBaselines();
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "更新失败" });
        } finally {
            setBaselinesBusy(false);
        }
    }

    async function deleteBaseline(bl: AdminBaseline) {
        if (!confirm(`删除 Baseline「${bl.display_name}」？`)) return;
        setBaselinesBusy(true);
        try {
            await adminDeleteBaseline(bl.id);
            setAdminMsg({ ok: true, text: `Baseline「${bl.display_name}」已删除` });
            void loadBaselines();
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "删除失败" });
        } finally {
            setBaselinesBusy(false);
        }
    }

    async function doAdminAction(fn: () => Promise<unknown>, successText: string) {
        try {
            await fn();
            setAdminMsg({ ok: true, text: `${successText} 成功` });
            void loadAdminData();
            void reload();
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "操作失败" });
        }
    }

    async function checkHealth() {
        setSysHealthBusy(true);
        try {
            const h = await adminGetSystem();
            setSysHealth(h);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "health check failed" });
        } finally {
            setSysHealthBusy(false);
        }
    }

    async function loadOverview() {
        try {
            const ov = await adminGetRoundOverview(roundId);
            setRoundOverview(ov);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "overview failed" });
        }
    }

    async function loadAllSubs() {
        try {
            const s = await adminGetAllSubmissions(roundId);
            setAllSubs(s);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "subs load failed" });
        }
    }

    async function loadAutoRoundConfig() {
        setAutoRoundBusy(true);
        try {
            const cfg = await adminGetAutoRoundConfig();
            setAutoRoundCfg(cfg);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "auto round config load failed" });
        } finally {
            setAutoRoundBusy(false);
        }
    }

    async function loadSiteConfig() {
        try {
            const cfg = await adminGetSiteConfig();
            setSiteCfg(cfg);
            setRegisterStatus(cfg);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "site config load failed" });
        }
    }

    async function loadRegistrationInvites() {
        try {
            const rows = await adminListRegistrationInvites();
            setAdminInvites(rows);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "invite load failed" });
        }
    }

    async function createInviteLink() {
        try {
            const row = await adminCreateRegistrationInvite({ max_uses: Math.max(1, inviteUses || 1) });
            setAdminMsg({ ok: true, text: `邀请链接已创建（${row.max_uses} 次）` });
            void loadRegistrationInvites();
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "invite create failed" });
        }
    }

    async function revokeInviteLink(inviteId: number) {
        try {
            await adminRevokeRegistrationInvite(inviteId);
            setAdminMsg({ ok: true, text: "邀请链接已撤销" });
            void loadRegistrationInvites();
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "invite revoke failed" });
        }
    }

    async function copyInviteLink(token: string) {
        const link = `${window.location.origin}${window.location.pathname}?invite=${encodeURIComponent(token)}`;
        try {
            await navigator.clipboard.writeText(link);
            setAdminMsg({ ok: true, text: "邀请链接已复制" });
        } catch {
            setAdminMsg({ ok: false, text: link });
        }
    }

    async function copyText(value: string, successText: string) {
        try {
            await navigator.clipboard.writeText(value);
            setAdminMsg({ ok: true, text: successText });
        } catch {
            setAdminMsg({ ok: false, text: value });
        }
    }

    async function openAgentTelemetry(userId: number) {
        setAgentTelemetryBusy(true);
        setAgentTelemetryOpen(true);
        setAgentTelemetryDetail(null);
        try {
            const data = await adminGetAgentTelemetry(userId);
            setAgentTelemetryDetail(data);
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "遥测数据加载失败" });
            setAgentTelemetryOpen(false);
        } finally {
            setAgentTelemetryBusy(false);
        }
    }

    async function doImportUsers() {
        if (!importText.trim()) return;
        setImportBusy(true);
        setImportResult(null);
        try {
            const result = await adminImportUsers(importText, importDryRun);
            setImportResult(result);
            if (!importDryRun && result.created_count > 0) {
                void loadAdminData();
            }
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "导入失败" });
        } finally {
            setImportBusy(false);
        }
    }

    async function doAdminResetPassword(userId: number, username: string) {
        if (!confirm(`确认重置用户「${username}」的密码？系统会生成一个新的随机密码。`)) return;
        try {
            const data = await adminResetPassword(userId);
            setResetPasswordResult({ username: data.username, password: data.password });
            setAdminMsg({ ok: true, text: `${data.username} 的密码已重置` });
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "密码重置失败" });
        }
    }

    async function saveSiteConfig() {
        if (!siteCfg) return;
        try {
            const saved = await adminUpdateSiteConfig({
                allow_registration: siteCfg.allow_registration,
                phase: siteCfg.phase ?? "competition",
                announcement_title: siteCfg.announcement_title ?? "",
                announcement_body: siteCfg.announcement_body ?? "",
            });
            setSiteCfg(saved);
            setRegisterStatus(saved);
            setAdminMsg({
                ok: true,
                text: `站点设置已保存：注册${saved.allow_registration ? "开启" : "关闭"}，阶段：${saved.phase === "test" ? "测试赛" : "正式赛"}，公告已发布`,
            });
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "site config save failed" });
        }
    }

    async function saveAutoRoundConfig() {
        if (!autoRoundCfg) return;
        setAutoRoundBusy(true);
        try {
            const saved = await adminUpdateAutoRoundConfig({
                enabled: autoRoundCfg.enabled,
                interval_minutes: autoRoundCfg.interval_minutes,
                competition_starts_at: autoRoundCfg.competition_starts_at,
                competition_ends_at: autoRoundCfg.competition_ends_at,
            });
            setAutoRoundCfg(saved);
            setAdminMsg({ ok: true, text: "无人值守配置已保存" });
            getStatus().then(setSvcStatus).catch(() => { });
        } catch (e) {
            setAdminMsg({ ok: false, text: e instanceof Error ? e.message : "auto round config save failed" });
        } finally {
            setAutoRoundBusy(false);
        }
    }

    async function saveAdminMap(draft: {
        name: string;
        source_text: string;
        sort_order: number;
        difficulty: number;
        is_active: boolean;
    }) {
        setMapSaveBusy(true);
        setMapSaveMsg(null);
        try {
            if (editingMap) {
                await adminUpdateMap(editingMap.id, draft);
                setAdminMsg({ ok: true, text: `地图 ${draft.name} 已更新` });
            } else {
                await adminCreateMap(draft);
                setAdminMsg({ ok: true, text: `地图 ${draft.name} 已创建` });
            }
            setMapEditorOpen(false);
            setEditingMap(null);
            void loadAdminMaps();
            void reload();
        } catch (e) {
            setMapSaveMsg(e instanceof Error ? e.message : "地图保存失败");
        } finally {
            setMapSaveBusy(false);
        }
    }

    async function handleMapUpload(e: React.ChangeEvent<HTMLInputElement>) {
        const files = Array.from(e.target.files ?? []);
        if (files.length === 0) return;
        e.target.value = "";
        setMapUploadBusy(true);
        setMapUploadMsg(null);
        try {
            const result: MapUploadResult = await adminUploadMaps(files);
            const ok = result.created.length;
            const fail = result.errors.length;
            const parts: string[] = [];
            if (ok > 0) parts.push(`成功导入 ${ok} 张地图`);
            if (fail > 0) parts.push(`${fail} 个文件解析失败`);
            setMapUploadMsg(parts.join("，") || "无变化");
            if (ok > 0) {
                void loadAdminMaps();
                void reload();
            }
        } catch (err) {
            setMapUploadMsg(err instanceof Error ? err.message : "上传失败");
        } finally {
            setMapUploadBusy(false);
        }
    }

    async function deleteAdminMap(mapId: number, name: string) {
        if (!confirm(`确认删除地图「${name}」？此操作不可恢复。`)) return;
        try {
            await adminDeleteMap(mapId);
            setAdminMsg({ ok: true, text: `地图「${name}」已删除` });
            void loadAdminMaps();
            void reload();
        } catch (err) {
            setAdminMsg({ ok: false, text: err instanceof Error ? err.message : "删除失败" });
        }
    }

    function downloadAdminMap(map: Pick<AdminMapTemplate, "name" | "slug" | "source_text">) {
        const blob = new Blob([map.source_text], { type: "text/plain;charset=utf-8" });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = url;
        anchor.download = mapDownloadFilename(map);
        document.body.appendChild(anchor);
        anchor.click();
        anchor.remove();
        URL.revokeObjectURL(url);
    }

    async function downloadVisibleMap(map: RoundMap) {
        const fallback = mapDownloadFilename({
            name: map.name ?? `map-${map.map_idx}`,
            slug: map.slug ?? map.seed,
        });
        if (svcStatus?.phase === "test") {
            await downloadTestMap(map.id, fallback);
            return;
        }
        await downloadRoundMap(roundId, map.id, fallback);
    }

    /* ── resize handlers ───────────────────────────────────── */
    function onSidebarResizeDown(e: React.PointerEvent<HTMLDivElement>) {
        const startX = e.clientX;
        const startW = sidebarWidth;
        const el = e.currentTarget;
        el.setPointerCapture(e.pointerId);
        const onMove = (ev: PointerEvent) => {
            setSidebarWidth(Math.max(140, Math.min(480, startW + ev.clientX - startX)));
        };
        const onUp = () => {
            el.removeEventListener("pointermove", onMove);
            el.removeEventListener("pointerup", onUp);
        };
        el.addEventListener("pointermove", onMove);
        el.addEventListener("pointerup", onUp);
    }

    function onDetailResizeDown(e: React.PointerEvent<HTMLDivElement>) {
        const startX = e.clientX;
        const startW = detailWidth;
        const el = e.currentTarget;
        el.setPointerCapture(e.pointerId);
        const onMove = (ev: PointerEvent) => {
            setDetailWidth(Math.max(200, Math.min(560, startW - (ev.clientX - startX))));
        };
        const onUp = () => {
            el.removeEventListener("pointermove", onMove);
            el.removeEventListener("pointerup", onUp);
        };
        el.addEventListener("pointermove", onMove);
        el.addEventListener("pointerup", onUp);
    }

    /* ── derived ────────────────────────────────────────────── */
    const lm = svcStatus?.phase === "test" ? testLive?.matches : live?.matches;
    const wsClass = (svcStatus?.phase === "test" ? testLive : live) ? "ws-live" : "ws-wait";
    const wsLabel = svcStatus?.phase === "test"
        ? (testLive ? `● ${zhStatus(testLive.test_run_status)}` : "○ 等待")
        : live
            ? `● ${zhStatus(live.round_status)}`
            : "○ 等待";
    const sortedRounds = [...rounds].sort((a, b) => b.id - a.id);
    const selectedRoundMeta = rounds.find(r => r.id === roundId) ?? null;
    const selectedRoundIndex = sortedRounds.findIndex(r => r.id === roundId);
    const canPrevRound = selectedRoundIndex >= 0 && selectedRoundIndex < sortedRounds.length - 1;
    const canNextRound = selectedRoundIndex > 0;
    const autoRoundCountdown = (() => {
        void nowTick;
        if (!svcStatus) return null;
        if (svcStatus.auto_round_state === "before_start" && svcStatus.competition_starts_at) {
            return `比赛开始 · ${fRemain(svcStatus.competition_starts_at)}`;
        }
        if (svcStatus.auto_round_state === "running" && svcStatus.next_round_at) {
            return `下一轮 第${svcStatus.next_round_id ?? "?"}轮 · ${fRemain(svcStatus.next_round_at)}`;
        }
        return null;
    })();
    const phaseMode = siteCfg?.phase ?? svcStatus?.phase ?? leaderboardPhase;
    const isTestPhase = phaseMode === "test";
    const hideRoundUiForPlayer = isTestPhase;
    const replayFrames = replayData?.frames ?? [];
    const currentReplayFrame = replayFrames[replayFrameIndex] ?? null;
    const prevReplayFrame = replayFrameIndex > 0 ? replayFrames[replayFrameIndex - 1] : null;
    const replayProgress = replayFrames.length > 1
        ? replayFrameIndex / (replayFrames.length - 1)
        : 0;

    /* ══════════════════════════════════════════════════════════ */
    if (!profile) {
        return (
            <div className="app" style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100vh" }}>
                <div className="panel" style={{ width: 280 }}>
                    <div className="sh" style={{ marginBottom: 10 }}>Asuri Major · 登录</div>
                    <div className="fr"><label>用户</label>
                        <input type="text" value={lUser} onChange={e => setLUser(e.target.value)}
                            onKeyDown={e => e.key === "Enter" && void doLogin()} autoFocus />
                    </div>
                    <div className="fr"><label>密码</label>
                        <input type="password" value={lPass} onChange={e => setLPass(e.target.value)}
                            onKeyDown={e => e.key === "Enter" && void doLogin()} />
                    </div>
                    <div className="btns" style={{ marginTop: 8 }}>
                        <button className="pri" onClick={() => void doLogin()}>登录</button>
                        <button
                            onClick={() => { setAuthMsg(null); setRegisterOpen(true); }}
                            disabled={registerStatus != null && !registerStatus.allow_registration && !registerInviteToken.trim()}
                        >注册</button>
                    </div>
                    {registerStatus != null && !registerStatus.allow_registration && !registerInviteToken.trim() && (
                        <div className="dim" style={{ fontSize: 11, marginTop: 4 }}>当前仅支持邀请链接注册</div>
                    )}
                    {authMsg && <div className={`msg ${authMsg.ok ? "ok" : "err"}`}>{authMsg.text}</div>}
                </div>
                <RegisterModal
                    open={registerOpen}
                    onClose={() => setRegisterOpen(false)}
                    username={rUser}
                    password={rPass}
                    onChangeUsername={setRUser}
                    onChangePassword={setRPass}
                    onSubmit={() => void doRegister()}
                    registerEnabled={registerStatus?.allow_registration ?? true}
                    inviteToken={registerInviteToken}
                    inviteStatus={inviteStatus}
                    authMsg={authMsg}
                />
            </div>
        );
    }

    return (
        <div className="app">

            {/* ── Topbar ── */}
            <div className="topbar">
                <span className="topbar-brand">Asuri Major</span>
                <span className="sep">│</span>
                <span className={wsClass}>{wsLabel}</span>
                {hideRoundUiForPlayer ? <>
                    <span className="sep">│</span>
                    <span className="tag"><b style={{ color: "var(--yellow)" }}>测试赛阶段</b></span>
                </> : <>
                    {autoRoundCountdown && <>
                        <span className="sep">│</span>
                        <span className="tag"><b style={{ color: "var(--yellow)" }}>{autoRoundCountdown}</b></span>
                    </>}
                </>}
                <div className="topbar-right">
                    {profile?.is_admin && <>
                        <span className="tag" style={{ display: "flex", gap: 6 }}>
                            {(["game", "admin"] as const).map(v => (
                                <span key={v} style={{ cursor: "pointer", color: view === v ? "var(--fg)" : "var(--fg3)" }}
                                    onClick={() => {
                                        setView(v);
                                        if (v === "admin") void loadAdminData();
                                    }}>
                                    {v === "game" ? "对局" : "★ 管理"}
                                </span>
                            ))}
                        </span>
                        <span className="sep">│</span>
                    </>}
                    <button className="tb-btn" onClick={() => setHelpOpen(v => !v)}>? 帮助</button>
                    <span className="sep">│</span>
                    {profile
                        ? <span className="tag"><b>{profileName}</b>{profile.is_admin ? " ★" : ""}{" "}<span className="dim">score {fScore(profile.score)}</span></span>
                        : <span className="ws-wait">访客</span>
                    }
                </div>
            </div>

            {/* ── Body ── */}
            <div className="body">

                {/* ── Sidebar ── */}
                <div className="sidebar" style={{ width: sidebarWidth, minWidth: sidebarWidth }}>
                    {!profile ? <>
                        <div className="sh">登录</div>
                        <div className="panel">
                            <div className="fr"><label>用户</label>
                                <input type="text" value={lUser} onChange={e => setLUser(e.target.value)}
                                    onKeyDown={e => e.key === "Enter" && void doLogin()} />
                            </div>
                            <div className="fr"><label>密码</label>
                                <input type="password" value={lPass} onChange={e => setLPass(e.target.value)}
                                    onKeyDown={e => e.key === "Enter" && void doLogin()} />
                            </div>
                            <div className="btns">
                                <button className="pri" onClick={() => void doLogin()}>登录</button>
                                <button
                                    onClick={() => {
                                        setAuthMsg(null);
                                        setRegisterOpen(true);
                                    }}
                                    disabled={registerStatus != null && !registerStatus.allow_registration && !registerInviteToken.trim()}
                                >
                                    注册
                                </button>
                            </div>
                            {registerStatus != null && !registerStatus.allow_registration && !registerInviteToken.trim() && (
                                <div className="dim" style={{ fontSize: 11, marginTop: 4 }}>当前仅支持邀请链接注册</div>
                            )}
                            {authMsg && <div className={`msg ${authMsg.ok ? "ok" : "err"}`}>{authMsg.text}</div>}
                        </div>
                    </> : <>
                        <div className="sh">会话</div>
                        <div className="panel">
                            <div style={{ marginBottom: 6 }}>
                                <b>{profileName}</b>
                                {profile.is_admin && <span className="dim"> ★ 管理员</span>}
                                <br />
                                <span className="dim">score {fScore(profile.score)}</span>
                                <span className="dim"> · id {profile.id}</span>
                            </div>
                            <div className="btns">
                                <button onClick={openChangePasswordModal}>改密码</button>
                                <button onClick={() => { setToken(""); setProfile(null); profileId.current = null; }}>退出</button>
                                <button onClick={() => me().then(u => { setProfile(u); profileId.current = u.id; setAccountMsg({ ok: true, text: "账号信息已刷新" }); }).catch(() => { })}>刷新</button>
                            </div>
                            {accountMsg && <div className={`msg ${accountMsg.ok ? "ok" : "err"}`}>{accountMsg.text}</div>}
                        </div>

                        <div className="sh">{hideRoundUiForPlayer ? "地图偏好" : `地图偏好 — round ${roundId}`}</div>
                        <div className="panel">
                            <div className="dim" style={{ fontSize: 11, marginBottom: 8 }}>
                                {hideRoundUiForPlayer
                                    ? "点击地图卡片加入或移除偏好列表。测试赛会优先按你的顺序选择训练图，并在提交后自动发起测试对局。"
                                    : "点击地图卡片加入/移除偏好列表，靠前的图被选中概率更高。每场对局选 1 张图，T/CT 各打一局。"}
                            </div>
                            {maps.length === 0
                                ? <div className="dim" style={{ fontSize: 11 }}>暂无地图</div>
                                : <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 10 }}>
                                    {maps.map(m => {
                                        const rank = mapPreferences.indexOf(m.map_idx);
                                        const preferred = rank !== -1;
                                        return (
                                            <div
                                                key={m.map_idx}
                                                onClick={() => toggleMapPreference(m.map_idx)}
                                                style={{
                                                    cursor: "pointer",
                                                    border: `1px solid ${preferred ? "var(--green)" : "var(--border)"}`,
                                                    background: preferred ? "var(--bg3)" : "var(--bg2)",
                                                    color: preferred ? "var(--green)" : "var(--fg2)",
                                                    borderRadius: 3,
                                                    padding: "3px 8px",
                                                    fontSize: 12,
                                                    userSelect: "none",
                                                    display: "flex",
                                                    alignItems: "center",
                                                    gap: 4,
                                                }}
                                            >
                                                {preferred && <span style={{ fontWeight: 700 }}>#{rank + 1}</span>}
                                                {m.name ?? m.slug ?? `map-${m.map_idx}`}
                                            </div>
                                        );
                                    })}
                                </div>
                            }
                            {mapPreferences.length > 0 && (
                                <div style={{ marginBottom: 8 }}>
                                    <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>偏好顺序（可调整）：</div>
                                    {mapPreferences.map((mapIdx, i) => {
                                        const m = maps.find(x => x.map_idx === mapIdx);
                                        const name = m ? (m.name ?? m.slug ?? `map-${mapIdx}`) : `map-${mapIdx}`;
                                        return (
                                            <div key={mapIdx} style={{ display: "flex", alignItems: "center", gap: 4, marginBottom: 3 }}>
                                                <span style={{ color: "var(--green)", fontSize: 11, width: 20 }}>#{i + 1}</span>
                                                <span style={{ fontSize: 12, flex: 1 }}>{name}</span>
                                                <button
                                                    style={{ fontSize: 10, padding: "1px 5px" }}
                                                    disabled={i === 0}
                                                    onClick={() => moveMapPreference(mapIdx, -1)}
                                                >↑</button>
                                                <button
                                                    style={{ fontSize: 10, padding: "1px 5px" }}
                                                    disabled={i === mapPreferences.length - 1}
                                                    onClick={() => moveMapPreference(mapIdx, 1)}
                                                >↓</button>
                                                <button
                                                    style={{ fontSize: 10, padding: "1px 5px", color: "var(--red)" }}
                                                    onClick={() => toggleMapPreference(mapIdx)}
                                                >×</button>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                            <div className="btns">
                                <button className="pri" onClick={() => void saveBp()}>保存</button>
                                <button onClick={() => void loadBp(roundId)}>加载</button>
                                <button onClick={() => void reload()}>↺</button>
                            </div>
                            {bpMsg && <div className={`msg ${bpMsg.ok ? "ok" : "err"}`}>{bpMsg.text}</div>}
                        </div>

                        <div className="sh" style={{ display: "flex", alignItems: "center" }}>
                            <span>{hideRoundUiForPlayer ? "当前测试模型" : "当前模型"}</span>
                            <button className="tb-btn" style={{ marginLeft: "auto", fontSize: 11 }}
                                onClick={() => {
                                    setSubHistoryOpen(v => !v);
                                    if (!subHistoryOpen) void getAllSubmissions().then(setSubHistory).catch(() => { });
                                }}>
                                历史{subHistory.length > 0 ? ` (${subHistory.length})` : ""}
                            </button>
                        </div>

                        {/* active models */}
                        <div className="panel">
                            {subList.length === 0
                                ? <div className="dim" style={{ fontSize: 11 }}>暂未提交模型</div>
                                : subList.map(s => (
                                    <div key={s.id ?? `${s.role}-${s.uploaded_at}`} style={{ fontSize: 12, display: "flex", alignItems: "center", gap: 6, marginBottom: 3 }}>
                                        <span style={{ color: "var(--fg3)", fontSize: 11, minWidth: 24 }}>{zhRole(s.role)}</span>
                                        <code style={{ color: "var(--blue)", fontSize: 11 }} title={s.id ?? undefined}>
                                            {modelIdLabel(s.id)}
                                        </code>
                                        <span className="dim" style={{ fontSize: 11 }}>{fTime(s.uploaded_at)}</span>
                                        {s.inherited && <span className="dim" style={{ fontSize: 10 }}>继承</span>}
                                    </div>
                                ))
                            }
                        </div>

                        {/* upload */}
                        <div className="panel" style={{ borderTop: "none" }}>
                            {!hideRoundUiForPlayer && svcStatus?.next_round_id != null && (
                                <div className="dim" style={{ fontSize: 11, marginBottom: 6 }}>
                                    将用于 <b style={{ color: "var(--fg2)" }}>第{svcStatus.next_round_id}轮</b>
                                    {svcStatus.next_round_at && <> · {fRemain(svcStatus.next_round_at)}</>}
                                </div>
                            )}
                            {hideRoundUiForPlayer && (
                                <div className="dim" style={{ fontSize: 11, marginBottom: 6 }}>
                                    新上传的模型会自动进入测试队列，与 Baseline 进行对局验证。
                                </div>
                            )}
                            <div className="fr">
                                <label>角色</label>
                                <select value={subRole} onChange={e => setSubRole(e.target.value as "attack" | "defense")}
                                    style={{ background: "var(--bg3)", border: "1px solid var(--border)", color: "var(--fg)", fontFamily: "inherit", fontSize: 12, padding: "2px 4px", flex: 1 }}>
                                    <option value="attack">进攻</option>
                                    <option value="defense">防守</option>
                                </select>
                            </div>
                            <div style={{ marginBottom: 4 }}>
                                <input type="file" accept=".safetensors"
                                    style={{ fontSize: 11, color: "var(--fg2)", width: "100%" }}
                                    onChange={e => setSubFile(e.target.files?.[0] ?? null)} />
                            </div>
                            {subFile && <div className="dim" style={{ fontSize: 11, marginBottom: 4, wordBreak: "break-all" }}>{subFile.name} ({(subFile.size / 1024).toFixed(0)} KB)</div>}
                            <div className="btns">
                                <button className="pri" disabled={subBusy || !subFile} onClick={() => void doUpload()}>
                                    {subBusy ? "上传中…" : "上传"}
                                </button>
                            </div>
                            {subMsg && <div className={`msg ${subMsg.ok ? "ok" : "err"}`}>{subMsg.text}</div>}
                        </div>

                        {/* upload history */}
                        {subHistoryOpen && (
                            <div className="panel" style={{ borderTop: "none", padding: 0 }}>
                                <div style={{ padding: "4px 8px", background: "var(--bg3)", borderBottom: "1px solid var(--border)", fontSize: 11, color: "var(--fg3)" }}>
                                    上传历史
                                </div>
                                {subHistory.length === 0
                                    ? <div className="dim" style={{ fontSize: 11, padding: "6px 8px" }}>暂无记录</div>
                                    : subHistory.map(s => (
                                        <div key={s.id ?? `${s.role}-${s.uploaded_at}`} style={{ display: "flex", alignItems: "center", gap: 6, padding: "4px 8px", borderBottom: "1px solid var(--border)", fontSize: 11 }}>
                                            <span style={{ color: "var(--fg3)", minWidth: 24 }}>{zhRole(s.role)}</span>
                                            <code style={{ color: "var(--blue)", flex: 1 }} title={s.id ?? undefined}>
                                                {modelIdLabel(s.id)}
                                            </code>
                                            <span className="dim" style={{ fontSize: 10 }}>{fTime(s.uploaded_at)}</span>
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    const modelId = s.id;
                                                    if (!modelId) {
                                                        setSubMsg({ ok: false, text: "模型 ID 不存在，无法下载" });
                                                        return;
                                                    }
                                                    void downloadSubmission(modelId).catch(err => setSubMsg({ ok: false, text: String(err instanceof Error ? err.message : err) }));
                                                }}
                                                style={{ color: "var(--fg3)", fontSize: 11, textDecoration: "none", padding: "1px 4px", border: "1px solid var(--border)", borderRadius: 2 }}
                                                title={`下载 ${modelIdLabel(s.id)}`}
                                            >↓</button>
                                        </div>
                                    ))
                                }
                            </div>
                        )}
                    </>}
                </div>

                <div className="resize-handle" onPointerDown={onSidebarResizeDown} />

                {/* ── Main content ── */}
                <div className="content">

                    {/* ══ ADMIN VIEW ══ */}
                    {view === "admin" && <>
                        {/* toolbar */}
                        <div className="sh" style={{ display: "flex", alignItems: "center", gap: 16 }}>
                            <span>管理控制台</span>
                            <span style={{ display: "flex", gap: 12, fontWeight: "normal", textTransform: "none", letterSpacing: 0 }}>
                                {(["rounds", "baselines", "maps", "users", "health", "overview", "subs", "auto"] as const).map(tab => (
                                    <span key={tab} style={{ cursor: "pointer", color: adminTab === tab ? "var(--fg)" : "var(--fg3)" }}
                                        onClick={() => {
                                            setAdminTab(tab);
                                            if (tab === "rounds" || tab === "users") void loadAdminData();
                                            if (tab === "baselines") void loadBaselines();
                                            if (tab === "maps") void loadAdminMaps();
                                            if (tab === "users") { void loadSiteConfig(); void loadRegistrationInvites(); }
                                            if (tab === "health") void checkHealth();
                                            if (tab === "overview") void loadOverview();
                                            if (tab === "subs") void loadAllSubs();
                                            if (tab === "auto") void loadAutoRoundConfig();
                                        }}>
                                        {tab === "rounds"
                                            ? "轮次"
                                            : tab === "baselines"
                                                ? "基线"
                                                : tab === "maps"
                                                    ? "地图池"
                                                    : tab === "users"
                                                        ? "用户"
                                                        : tab === "health"
                                                            ? "系统健康"
                                                            : tab === "overview"
                                                                ? "参赛概览"
                                                                : tab === "subs"
                                                                    ? "所有提交"
                                                                    : "无人值守"}
                                    </span>
                                ))}
                            </span>
                            <span style={{ marginLeft: "auto" }}>
                                {adminMsg && <span className={adminMsg.ok ? "pos" : "neg"} style={{ fontSize: 12 }}>{adminMsg.text}</span>}
                            </span>
                        </div>

                        {/* ── rounds tab ── */}
                        {adminTab === "rounds" && <>
                            <div style={{ padding: 12, display: "grid", gridTemplateColumns: "repeat(4, minmax(160px, 1fr))", gap: 12, borderBottom: "1px solid var(--border)" }}>
                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="dim" style={{ fontSize: 11 }}>赛程状态</div>
                                    <div style={{ marginTop: 4 }}>{zhScheduleState(svcStatus?.auto_round_state ?? "disabled")}</div>
                                </div>
                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="dim" style={{ fontSize: 11 }}>比赛时间</div>
                                    <div style={{ marginTop: 4, fontSize: 12, lineHeight: 1.6 }}>
                                        {svcStatus?.competition_starts_at ? fTime(svcStatus.competition_starts_at, true) : "—"}
                                        <br />
                                        {svcStatus?.competition_ends_at ? fTime(svcStatus.competition_ends_at, true) : "—"}
                                    </div>
                                </div>
                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="dim" style={{ fontSize: 11 }}>轮次间隔</div>
                                    <div style={{ marginTop: 4 }}>{svcStatus?.round_interval_minutes ?? autoRoundCfg?.interval_minutes ?? "—"} 分钟</div>
                                </div>
                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="dim" style={{ fontSize: 11 }}>下一自动轮次</div>
                                    <div style={{ marginTop: 4, fontSize: 12, lineHeight: 1.6 }}>
                                        {svcStatus?.next_round_id != null ? `第${svcStatus.next_round_id}轮` : "—"}
                                        <br />
                                        {svcStatus?.next_round_at ? fTime(svcStatus.next_round_at, true) : "—"}
                                    </div>
                                </div>
                            </div>

                            <div className="round-create-bar">
                                <button className="pri" onClick={() => void doAdminAction(
                                    () => adminCreateRound(true),
                                    isTestPhase ? "测试轮次已启动" : "已手动补一轮"
                                )}>▶ {isTestPhase ? "启动测试轮次" : "手动补一轮"}</button>
                                {!isTestPhase && (
                                    <span className="dim" style={{ fontSize: 11 }}>
                                        自动建轮由“无人值守”中的赛程配置驱动；这里用于补轮、删轮和干预异常轮次。
                                    </span>
                                )}
                                <button style={{ marginLeft: "auto" }} onClick={() => { void loadAdminData(); void loadAutoRoundConfig(); getStatus().then(setSvcStatus).catch(() => { }); }}>↺</button>
                            </div>

                            <div className="tbl-wrap" style={{ flex: 1 }}>
                                <table>
                                    <thead><tr>
                                        <th className="r" style={{ width: 56 }}>轮次</th>
                                        <th style={{ width: 72 }}>来源</th>
                                        <th style={{ width: 72 }}>状态</th>
                                        <th>创建时间</th>
                                        <th style={{ width: 220 }}>操作</th>
                                    </tr></thead>
                                    <tbody>
                                        {adminRounds.length === 0
                                            ? <tr><td colSpan={5} className="dim" style={{ padding: "8px 10px" }}>暂无轮次</td></tr>
                                            : adminRounds.map(r => (
                                                <tr key={r.id}>
                                                    <td className="r dim">{r.id}</td>
                                                    <td className="dim">{r.created_mode === "auto" ? "自动" : r.created_mode === "test" ? "测试" : "手动"}</td>
                                                    <td className={`s-${r.status}`}>{zhStatus(r.status)}</td>
                                                    <td className="dim">{fTime(r.created_at, true)}</td>
                                                    <td>
                                                        <span style={{ display: "flex", gap: 4 }}>
                                                            <button className="sm" style={{ color: "var(--red)" }}
                                                                onClick={() => {
                                                                    if (confirm(`删除第${r.id}轮？对局、积分历史将一并清除，不可撤销。`))
                                                                        void doAdminAction(() => adminDeleteRound(r.id), `第${r.id}轮已删除`).then(() => void loadAdminData());
                                                                }}>
                                                                删除
                                                            </button>
                                                            {r.status === "running" && r.created_mode !== "test" && (
                                                                <button className="sm pri"
                                                                    onClick={() => void doAdminAction(() => adminPipelineRound(r.id), `第${r.id}轮运行中`)}>
                                                                    继续运行
                                                                </button>
                                                            )}
                                                            {r.status === "running" && r.created_mode !== "test" && (
                                                                <button className="sm"
                                                                    onClick={() => void doAdminAction(() => adminFinalizeRound(r.id), `第${r.id}轮结算中`)}>
                                                                    强制结算
                                                                </button>
                                                            )}
                                                            {r.created_mode !== "test" && (
                                                                <button className="sm" style={{ color: "var(--yellow)" }}
                                                                    onClick={() => {
                                                                        if (confirm(`重测第${r.id}轮？该轮已有对局结果与积分影响会被清空，然后重新排队执行。`))
                                                                            void doAdminAction(() => adminRerunRound(r.id), `第${r.id}轮已重新开始`).then(() => void loadAdminData());
                                                                    }}>
                                                                    重测
                                                                </button>
                                                            )}
                                                            {r.status === "running" && r.created_mode !== "test" && (
                                                                <button className="sm" style={{ color: "var(--yellow)" }}
                                                                    onClick={() => void doAdminAction(() => adminResetFailed(r.id), `第${r.id}轮失败已重试`)}>
                                                                    重试失败
                                                                </button>
                                                            )}
                                                        </span>
                                                    </td>
                                                </tr>
                                            ))
                                        }
                                    </tbody>
                                </table>
                            </div>
                        </>}

                        {/* ── baselines tab ── */}
                        {adminTab === "baselines" && (() => {
                            const atkSubs = adminAllSubs.filter(s => s.role === "attack");
                            const defSubs = adminAllSubs.filter(s => s.role === "defense");
                            const subLabel = (s: AdminSubmission) =>
                                `#${s.id} ${s.username} — ${fTime(s.uploaded_at, true)}${s.file_hash ? ` (${s.file_hash.slice(0, 8)})` : ""}`;
                            return <>
                                {/* toolbar */}
                                <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6, alignItems: "center" }}>
                                    <button onClick={() => void loadBaselines()} disabled={baselinesBusy}>
                                        {baselinesBusy ? "加载中…" : "↺ 刷新"}
                                    </button>
                                    <span className="dim" style={{ fontSize: 11 }}>
                                        {adminBaselines.length} 个 Baseline，{adminAllSubs.length} 个提交可选
                                    </span>
                                </div>

                                <div style={{ display: "flex", flexDirection: "column", gap: 0, overflowY: "auto", flex: 1 }}>
                                    {/* ── existing baselines list ── */}
                                    <div style={{ padding: "10px 12px 0 12px" }}>
                                        <div style={{ fontWeight: 600, fontSize: 12, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--fg3)", marginBottom: 8 }}>
                                            当前 Baselines
                                        </div>
                                        {adminBaselines.length === 0 ? (
                                            <div className="dim" style={{ fontSize: 12, padding: "8px 0" }}>暂无 Baseline，在下方创建第一个</div>
                                        ) : (
                                            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                                                {adminBaselines.map(bl => (
                                                    <div key={bl.id} style={{
                                                        border: `1px solid ${bl.is_active ? "var(--border)" : "var(--fg3)"}`,
                                                        background: "var(--bg2)",
                                                        padding: "10px 12px",
                                                        opacity: bl.is_active ? 1 : 0.6,
                                                    }}>
                                                        {editingBaseline?.id === bl.id ? (
                                                            /* ── inline edit form ── */
                                                            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                                                                <div className="fr">
                                                                    <label style={{ minWidth: 72, fontSize: 12 }}>显示名</label>
                                                                    <input
                                                                        style={{ flex: 1 }}
                                                                        value={editingBaseline.display_name}
                                                                        onChange={e => setEditingBaseline(prev => prev ? { ...prev, display_name: e.target.value } : prev)}
                                                                    />
                                                                </div>
                                                                <div className="fr">
                                                                    <label style={{ minWidth: 72, fontSize: 12 }}>排序</label>
                                                                    <input
                                                                        type="number"
                                                                        style={{ width: 80 }}
                                                                        value={editingBaseline.sort_order}
                                                                        onChange={e => setEditingBaseline(prev => prev ? { ...prev, sort_order: Number(e.target.value) } : prev)}
                                                                    />
                                                                </div>
                                                                <div className="fr">
                                                                    <label style={{ minWidth: 72, fontSize: 12 }}>启用</label>
                                                                    <input
                                                                        type="checkbox"
                                                                        checked={editingBaseline.is_active}
                                                                        onChange={e => setEditingBaseline(prev => prev ? { ...prev, is_active: e.target.checked } : prev)}
                                                                    />
                                                                </div>
                                                                <div style={{ display: "flex", gap: 6, marginTop: 2 }}>
                                                                    <button className="sm pri" onClick={() => void saveEditingBaseline()} disabled={baselinesBusy}>保存</button>
                                                                    <button className="sm" onClick={() => setEditingBaseline(null)}>取消</button>
                                                                </div>
                                                            </div>
                                                        ) : (
                                                            /* ── read view ── */
                                                            <div style={{ display: "flex", gap: 10, alignItems: "flex-start", flexWrap: "wrap" }}>
                                                                <div style={{ flex: 1, minWidth: 180 }}>
                                                                    <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
                                                                        <span style={{
                                                                            fontWeight: 700,
                                                                            fontSize: 14,
                                                                            color: bl.is_active ? "var(--blue)" : "var(--fg3)",
                                                                        }}>
                                                                            {bl.display_name}
                                                                        </span>
                                                                        <span style={{
                                                                            fontSize: 10,
                                                                            padding: "1px 5px",
                                                                            border: `1px solid ${bl.is_active ? "var(--green)" : "var(--fg3)"}`,
                                                                            color: bl.is_active ? "var(--green)" : "var(--fg3)",
                                                                        }}>
                                                                            {bl.is_active ? "启用" : "停用"}
                                                                        </span>
                                                                        <span className="dim" style={{ fontSize: 10 }}>#{bl.id} · 排序 {bl.sort_order}</span>
                                                                    </div>
                                                                    <div style={{ fontSize: 11, color: "var(--fg3)", lineHeight: 1.7 }}>
                                                                        <span>攻击 sub#{bl.attack_submission_id}</span>
                                                                        <span style={{ margin: "0 8px" }}>·</span>
                                                                        <span>防守 sub#{bl.defense_submission_id}</span>
                                                                    </div>
                                                                </div>
                                                                <div style={{ display: "flex", gap: 5, flexShrink: 0, alignSelf: "center" }}>
                                                                    <button className="sm" onClick={() => setEditingBaseline({ ...bl })}>编辑</button>
                                                                    <button
                                                                        className="sm"
                                                                        style={{ color: "var(--red)" }}
                                                                        onClick={() => void deleteBaseline(bl)}
                                                                        disabled={baselinesBusy}
                                                                    >
                                                                        删除
                                                                    </button>
                                                                </div>
                                                            </div>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                        )}
                                    </div>

                                    {/* ── create baseline form ── */}
                                    <div style={{ padding: "16px 12px 16px 12px" }}>
                                        <div style={{ fontWeight: 600, fontSize: 12, letterSpacing: "0.06em", textTransform: "uppercase", color: "var(--fg3)", marginBottom: 8 }}>
                                            新建 Baseline
                                        </div>
                                        <div style={{ display: "flex", flexDirection: "column", gap: 8, border: "1px solid var(--border)", padding: "12px", background: "var(--bg2)" }}>
                                            <div className="fr">
                                                <label style={{ minWidth: 84, fontSize: 12 }}>显示名</label>
                                                <input
                                                    placeholder="例：官方 Baseline v1"
                                                    style={{ flex: 1 }}
                                                    value={blName}
                                                    onChange={e => setBlName(e.target.value)}
                                                />
                                            </div>
                                            {/* ── attack submission picker ── */}
                                            {(() => {
                                                const q = blAtkSearch.toLowerCase();
                                                const filtered = atkSubs.filter(s =>
                                                    !q || s.username.toLowerCase().includes(q) || String(s.id).includes(q) || (s.file_hash ?? "").toLowerCase().includes(q)
                                                );
                                                const selected = atkSubs.find(s => s.id === blAtkId);
                                                return (
                                                    <div style={{ display: "flex", gap: 8 }}>
                                                        <label style={{ minWidth: 84, fontSize: 12, paddingTop: 4, flexShrink: 0 }}>攻击提交</label>
                                                        <div style={{ flex: 1 }}>
                                                            <input
                                                                placeholder="搜索用户名 / sub ID / hash…"
                                                                value={blAtkSearch}
                                                                onChange={e => setBlAtkSearch(e.target.value)}
                                                                style={{ width: "100%", marginBottom: 4 }}
                                                            />
                                                            <div style={{ maxHeight: 140, overflowY: "auto", border: "1px solid var(--border)", background: "var(--bg)" }}>
                                                                {filtered.length === 0
                                                                    ? <div className="dim" style={{ padding: "6px 10px", fontSize: 11 }}>无匹配结果</div>
                                                                    : filtered.map(s => (
                                                                        <div
                                                                            key={s.id}
                                                                            onClick={() => setBlAtkId(s.id)}
                                                                            style={{
                                                                                padding: "5px 10px",
                                                                                cursor: "pointer",
                                                                                fontSize: 12,
                                                                                background: blAtkId === s.id ? "var(--blue)" : "transparent",
                                                                                color: blAtkId === s.id ? "#fff" : "var(--fg)",
                                                                            }}
                                                                        >
                                                                            {subLabel(s)}
                                                                        </div>
                                                                    ))
                                                                }
                                                            </div>
                                                            {selected && (
                                                                <div style={{ fontSize: 11, marginTop: 3, color: "var(--blue)" }}>
                                                                    已选：{subLabel(selected)}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                            {/* ── defense submission picker ── */}
                                            {(() => {
                                                const q = blDefSearch.toLowerCase();
                                                const filtered = defSubs.filter(s =>
                                                    !q || s.username.toLowerCase().includes(q) || String(s.id).includes(q) || (s.file_hash ?? "").toLowerCase().includes(q)
                                                );
                                                const selected = defSubs.find(s => s.id === blDefId);
                                                return (
                                                    <div style={{ display: "flex", gap: 8 }}>
                                                        <label style={{ minWidth: 84, fontSize: 12, paddingTop: 4, flexShrink: 0 }}>防守提交</label>
                                                        <div style={{ flex: 1 }}>
                                                            <input
                                                                placeholder="搜索用户名 / sub ID / hash…"
                                                                value={blDefSearch}
                                                                onChange={e => setBlDefSearch(e.target.value)}
                                                                style={{ width: "100%", marginBottom: 4 }}
                                                            />
                                                            <div style={{ maxHeight: 140, overflowY: "auto", border: "1px solid var(--border)", background: "var(--bg)" }}>
                                                                {filtered.length === 0
                                                                    ? <div className="dim" style={{ padding: "6px 10px", fontSize: 11 }}>无匹配结果</div>
                                                                    : filtered.map(s => (
                                                                        <div
                                                                            key={s.id}
                                                                            onClick={() => setBlDefId(s.id)}
                                                                            style={{
                                                                                padding: "5px 10px",
                                                                                cursor: "pointer",
                                                                                fontSize: 12,
                                                                                background: blDefId === s.id ? "var(--blue)" : "transparent",
                                                                                color: blDefId === s.id ? "#fff" : "var(--fg)",
                                                                            }}
                                                                        >
                                                                            {subLabel(s)}
                                                                        </div>
                                                                    ))
                                                                }
                                                            </div>
                                                            {selected && (
                                                                <div style={{ fontSize: 11, marginTop: 3, color: "var(--blue)" }}>
                                                                    已选：{subLabel(selected)}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })()}
                                            <div className="fr">
                                                <label style={{ minWidth: 84, fontSize: 12 }}>排序顺序</label>
                                                <input
                                                    type="number"
                                                    style={{ width: 80 }}
                                                    value={blSortOrder}
                                                    onChange={e => setBlSortOrder(Number(e.target.value))}
                                                />
                                                <span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>数字小的排在前面</span>
                                            </div>
                                            <div style={{ display: "flex", gap: 6, marginTop: 4 }}>
                                                <button
                                                    className="pri"
                                                    onClick={() => void createBaseline()}
                                                    disabled={baselinesBusy || !blName.trim() || blAtkId === "" || blDefId === ""}
                                                >
                                                    创建 Baseline
                                                </button>
                                                {adminAllSubs.length === 0 && (
                                                    <span className="dim" style={{ fontSize: 11, alignSelf: "center" }}>
                                                        暂无提交可选，请先在其他账户上传模型
                                                    </span>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </>;
                        })()}

                        {adminTab === "maps" && <>
                            <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap" }}>
                                <button onClick={() => void loadAdminMaps()}>↺ 刷新</button>
                                <button
                                    className="pri"
                                    onClick={() => {
                                        setEditingMap(null);
                                        setMapSaveMsg(null);
                                        setMapEditorOpen(true);
                                    }}
                                >
                                    + 新建地图
                                </button>
                                <input
                                    ref={mapUploadRef}
                                    type="file"
                                    multiple
                                    accept=".txt"
                                    style={{ display: "none" }}
                                    onChange={e => void handleMapUpload(e)}
                                />
                                <button
                                    disabled={mapUploadBusy}
                                    onClick={() => { setMapUploadMsg(null); mapUploadRef.current?.click(); }}
                                >
                                    {mapUploadBusy ? "上传中…" : "↑ 上传地图(.txt)"}
                                </button>
                                {mapUploadMsg && (
                                    <span className="dim" style={{ fontSize: 11 }}>{mapUploadMsg}</span>
                                )}
                                {!mapUploadMsg && (
                                    <span className="dim" style={{ fontSize: 11, marginLeft: 4 }}>
                                        支持多选 .txt 文件批量上传；创建轮次时会快照当前地图池。
                                    </span>
                                )}
                            </div>
                            <div className="tbl-wrap" style={{ flex: 1 }}>
                                <table>
                                    <thead><tr>
                                        <th className="r" style={{ width: 48 }}>排序</th>
                                        <th>名称</th>
                                        <th style={{ width: 120 }}>slug</th>
                                        <th className="r" style={{ width: 70 }}>难度</th>
                                        <th className="r" style={{ width: 70 }}>障碍</th>
                                        <th style={{ width: 70 }}>状态</th>
                                        <th style={{ width: 140 }}>更新时间</th>
                                        <th style={{ width: 90 }}>操作</th>
                                    </tr></thead>
                                    <tbody>
                                        {adminMaps.length === 0
                                            ? <tr><td colSpan={8} className="dim" style={{ padding: "8px 10px" }}>暂无地图</td></tr>
                                            : adminMaps.map(row => {
                                                const layout = row.layout as Record<string, unknown>;
                                                const obstacles = (layout.obstacles as number[][] | undefined) ?? [];
                                                return (
                                                    <tr key={row.id}>
                                                        <td className="r dim">{row.sort_order}</td>
                                                        <td><b>{row.name}</b></td>
                                                        <td className="dim">{row.slug}</td>
                                                        <td className="r">{row.difficulty.toFixed(2)}</td>
                                                        <td className="r">{obstacles.length}</td>
                                                        <td style={{ color: row.is_active ? "var(--green)" : "var(--fg3)" }}>
                                                            {row.is_active ? "启用" : "停用"}
                                                        </td>
                                                        <td className="dim">{fTime(row.updated_at, true)}</td>
                                                        <td style={{ display: "flex", gap: 4 }}>
                                                            <button
                                                                className="sm"
                                                                onClick={() => downloadAdminMap(row)}
                                                            >
                                                                下载
                                                            </button>
                                                            <button
                                                                className="sm"
                                                                onClick={() => {
                                                                    setEditingMap(row);
                                                                    setMapSaveMsg(null);
                                                                    setMapEditorOpen(true);
                                                                }}
                                                            >
                                                                编辑
                                                            </button>
                                                            <button
                                                                className="sm neg"
                                                                onClick={() => void deleteAdminMap(row.id, row.name)}
                                                            >
                                                                删除
                                                            </button>
                                                        </td>
                                                    </tr>
                                                );
                                            })
                                        }
                                    </tbody>
                                </table>
                            </div>
                        </>}

                        {/* ── users tab ── */}
                        {adminTab === "users" && profile && (
                            <AdminUsersTab
                                profile={profile}
                                siteCfg={siteCfg}
                                setSiteCfg={setSiteCfg}
                                adminUsers={adminUsers}
                                adminInvites={adminInvites}
                                showInviteList={showInviteList}
                                setShowInviteList={setShowInviteList}
                                inviteUses={inviteUses}
                                setInviteUses={setInviteUses}
                                importText={importText}
                                setImportText={setImportText}
                                importResult={importResult}
                                setImportResult={setImportResult}
                                importDryRun={importDryRun}
                                setImportDryRun={setImportDryRun}
                                importBusy={importBusy}
                                resetPasswordResult={resetPasswordResult}
                                setResetPasswordResult={setResetPasswordResult}
                                onRefresh={() => { void loadAdminData(); void loadSiteConfig(); void loadRegistrationInvites(); }}
                                onSaveSiteConfig={() => void saveSiteConfig()}
                                onCreateInviteLink={() => void createInviteLink()}
                                onCopyInviteLink={(token) => void copyInviteLink(token)}
                                onRevokeInviteLink={(id) => void revokeInviteLink(id)}
                                onImportUsers={() => void doImportUsers()}
                                onCopyText={(value, label) => void copyText(value, label)}
                                onToggleActive={(id, username, isActive) => void doAdminAction(() => adminToggleActive(id), `${username} 已${isActive ? "停用" : "启用"}`)}
                                onToggleAdmin={(id, username, isAdmin) => void doAdminAction(() => adminToggleAdmin(id), `${username} 管理员权限已${isAdmin ? "撤销" : "授予"}`)}
                                onToggleSpectator={(id, username, isSpectator) => void doAdminAction(() => adminToggleSpectator(id), `${username} 已${isSpectator ? "取消观战" : "设为观战"}`)}
                                onResetScore={(id, username) => void doAdminAction(() => adminResetScore(id), `${username} 积分已重置`)}
                                onResetPassword={(id, username) => void doAdminResetPassword(id, username)}
                                onOpenAgentTelemetry={(id) => void openAgentTelemetry(id)}
                            />
                        )}

                        {/* ── health tab ── */}
                        {adminTab === "health" && <>
                            <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)" }}>
                                <button onClick={() => void checkHealth()} disabled={sysHealthBusy}>
                                    {sysHealthBusy ? "检查中…" : "↺ 刷新"}
                                </button>
                            </div>
                            <div style={{ padding: 16, display: "flex", gap: 24, flexWrap: "wrap" }}>
                                {sysHealth ? <>
                                    {([
                                        ["数据库", sysHealth.db ? "✓ 正常" : "✗ 异常", sysHealth.db],
                                        ["Redis", sysHealth.redis ? "✓ 正常" : "✗ 异常", sysHealth.redis],
                                        [`Celery Workers`, String(sysHealth.celery_workers), sysHealth.celery_workers > 0],
                                        [`活跃任务`, String(sysHealth.celery_active_tasks), true],
                                    ] as [string, string, boolean][]).map(([label, val, ok]) => (
                                        <div key={label} style={{ background: "var(--bg3)", border: "1px solid var(--border)", padding: "12px 20px", minWidth: 140 }}>
                                            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>{label}</div>
                                            <div style={{ fontSize: 18, fontWeight: "bold", color: ok ? "var(--green)" : "var(--red)" }}>{val}</div>
                                        </div>
                                    ))}
                                </> : <div className="dim" style={{ fontSize: 12 }}>点击刷新获取系统状态</div>}
                            </div>
                        </>}

                        {/* ── overview tab ── */}
                        {adminTab === "overview" && <>
                            <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)" }}>
                                <button onClick={() => void loadOverview()}>↺ 刷新 r{roundId}</button>
                                <span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>当前查看 round {roundId}（在顶栏切换）</span>
                            </div>
                            <div className="tbl-wrap" style={{ flex: 1 }}>
                                <table>
                                    <thead><tr>
                                        <th>用户</th>
                                        <th className="r" style={{ width: 60 }}>攻击模型</th>
                                        <th className="r" style={{ width: 60 }}>防守模型</th>
                                        <th className="r" style={{ width: 50 }}>BP</th>
                                        <th className="r" style={{ width: 60 }}>总对局</th>
                                        <th className="r" style={{ width: 60 }}>排队</th>
                                        <th className="r" style={{ width: 60 }}>进行中</th>
                                        <th className="r" style={{ width: 60 }}>已完成</th>
                                        <th className="r" style={{ width: 60 }}>失败</th>
                                    </tr></thead>
                                    <tbody>
                                        {roundOverview.length === 0
                                            ? <tr><td colSpan={9} className="dim" style={{ padding: "8px 10px" }}>暂无数据，点击刷新</td></tr>
                                            : roundOverview.map(u => (
                                                <tr key={u.user_id} style={{ color: u.has_attack_sub && u.has_defense_sub && u.has_bp ? "var(--fg)" : "var(--yellow)" }}>
                                                    <td><b>{u.username}</b></td>
                                                    <td className="r"><span style={{ color: u.has_attack_sub ? "var(--green)" : "var(--red)" }}>{u.has_attack_sub ? "✓" : "✗"}</span></td>
                                                    <td className="r"><span style={{ color: u.has_defense_sub ? "var(--green)" : "var(--red)" }}>{u.has_defense_sub ? "✓" : "✗"}</span></td>
                                                    <td className="r"><span style={{ color: u.has_bp ? "var(--green)" : "var(--red)" }}>{u.has_bp ? "✓" : "✗"}</span></td>
                                                    <td className="r">{u.matches_total || "—"}</td>
                                                    <td className="r dim">{u.matches_queued || "—"}</td>
                                                    <td className="r dim">{u.matches_running || "—"}</td>
                                                    <td className="r pos">{u.matches_completed || "—"}</td>
                                                    <td className="r" style={{ color: u.matches_failed > 0 ? "var(--red)" : undefined }}>{u.matches_failed || "—"}</td>
                                                </tr>
                                            ))
                                        }
                                    </tbody>
                                </table>
                            </div>
                        </>}

                        {/* ── subs tab ── */}
                        {adminTab === "subs" && <>
                            <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)" }}>
                                <button onClick={() => void loadAllSubs()}>↺ 刷新 r{roundId}</button>
                                <span className="dim" style={{ fontSize: 11, marginLeft: 8 }}>当前查看 round {roundId}（在顶栏切换）</span>
                            </div>
                            <div className="tbl-wrap" style={{ flex: 1 }}>
                                <table>
                                    <thead><tr>
                                        <th className="r" style={{ width: 40 }}>ID</th>
                                        <th>用户</th>
                                        <th style={{ width: 80 }}>角色</th>
                                        <th>上传时间</th>
                                    </tr></thead>
                                    <tbody>
                                        {allSubs.length === 0
                                            ? <tr><td colSpan={4} className="dim" style={{ padding: "8px 10px" }}>暂无提交，点击刷新</td></tr>
                                            : allSubs.map(s => (
                                                <tr key={s.id}>
                                                    <td className="r dim">{s.id}</td>
                                                    <td><b>{s.username}</b></td>
                                                    <td className="dim">{zhRole(s.role)}</td>
                                                    <td className="dim">{fTime(s.uploaded_at, true)}</td>
                                                </tr>
                                            ))
                                        }
                                    </tbody>
                                </table>
                            </div>
                        </>}

                        {/* ── auto tab ── */}
                        {adminTab === "auto" && <>
                            <div style={{ padding: "6px 10px", borderBottom: "1px solid var(--border)", display: "flex", gap: 6 }}>
                                <button onClick={() => void loadAutoRoundConfig()} disabled={autoRoundBusy}>
                                    {autoRoundBusy ? "加载中…" : "↺ 刷新"}
                                </button>
                                <button className="pri" onClick={() => void saveAutoRoundConfig()} disabled={autoRoundBusy || !autoRoundCfg}>
                                    保存赛程
                                </button>
                            </div>

                            <div style={{ padding: 12, display: "grid", gridTemplateColumns: "repeat(2, minmax(260px, 1fr))", gap: 12 }}>
                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="fr" style={{ marginBottom: 8 }}>
                                        <label style={{ minWidth: 82 }}>启用赛程</label>
                                        <input
                                            type="checkbox"
                                            checked={Boolean(autoRoundCfg?.enabled)}
                                            onChange={e => setAutoRoundCfg(prev => prev ? { ...prev, enabled: e.target.checked } : prev)}
                                            disabled={!autoRoundCfg}
                                        />
                                    </div>
                                    <div className="fr">
                                        <label style={{ minWidth: 70 }}>轮次间隔</label>
                                        <input
                                            type="number"
                                            min={1}
                                            max={1440}
                                            value={autoRoundCfg?.interval_minutes ?? 10}
                                            onChange={e => setAutoRoundCfg(prev => prev ? { ...prev, interval_minutes: Number(e.target.value) || 10 } : prev)}
                                            disabled={!autoRoundCfg}
                                        />
                                        <span className="dim" style={{ fontSize: 11 }}>分钟</span>
                                    </div>
                                    <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                                        轮次会在比赛开始时间起，按固定间隔自动生成；结束时间到达后停止自动建轮。
                                    </div>
                                </div>

                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="fr">
                                        <label style={{ minWidth: 88 }}>比赛开始</label>
                                        <input
                                            type="datetime-local"
                                            value={toDatetimeLocalValue(autoRoundCfg?.competition_starts_at)}
                                            onChange={e => setAutoRoundCfg(prev => prev ? { ...prev, competition_starts_at: fromDatetimeLocalValue(e.target.value) } : prev)}
                                            disabled={!autoRoundCfg}
                                        />
                                    </div>
                                    <div className="fr">
                                        <label style={{ minWidth: 88 }}>比赛结束</label>
                                        <input
                                            type="datetime-local"
                                            value={toDatetimeLocalValue(autoRoundCfg?.competition_ends_at)}
                                            onChange={e => setAutoRoundCfg(prev => prev ? { ...prev, competition_ends_at: fromDatetimeLocalValue(e.target.value) } : prev)}
                                            disabled={!autoRoundCfg}
                                        />
                                    </div>
                                    <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                                        当前状态：{zhScheduleState(autoRoundCfg?.schedule_state ?? "disabled")}
                                        {autoRoundCfg?.next_slot_at && <> · 下一时槽 {fTime(autoRoundCfg.next_slot_at, true)}</>}
                                    </div>
                                    {autoRoundCfg?.updated_at && (
                                        <div className="dim" style={{ fontSize: 11, marginTop: 6 }}>
                                            最近更新: {fTime(autoRoundCfg.updated_at, true)}
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div style={{ padding: "0 12px 12px 12px" }}>
                                <div className="panel" style={{ border: "1px solid var(--border)", borderBottom: "1px solid var(--border)" }}>
                                    <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>环境变量默认值（仅供参考）</div>
                                    {autoRoundCfg?.env_defaults ? (
                                        <div style={{ fontSize: 12, lineHeight: 1.7 }}>
                                            <div>enabled: {String(autoRoundCfg.env_defaults.enabled)}</div>
                                            <div>interval_minutes: {autoRoundCfg.env_defaults.interval_minutes}</div>
                                            <div>competition_starts_at: {autoRoundCfg.env_defaults.competition_starts_at ?? "—"}</div>
                                            <div>competition_ends_at: {autoRoundCfg.env_defaults.competition_ends_at ?? "—"}</div>
                                            <div>tick_seconds: {autoRoundCfg.env_defaults.tick_seconds}</div>
                                            <div>reconcile_seconds: {autoRoundCfg.env_defaults.reconcile_seconds}</div>
                                        </div>
                                    ) : <div className="dim" style={{ fontSize: 12 }}>暂无</div>}
                                </div>
                            </div>
                        </>}
                    </>}

                    {/* ══ GAME VIEW ══ */}
                    {view === "game" && <div className="game-view">

                        {isTestPhase && (
                            <div className="game-summary-section">
                                <div className="sh">版本评测
                                    <span style={{ float: "right", fontWeight: "normal", textTransform: "none", letterSpacing: 0 }} className="dim">
                                        {profile?.is_admin ? "当前显示全员测试对局记录" : "当前显示我的最新测试结果"}
                                    </span>
                                </div>
                                <div className="panel">
                                    {testStatus?.latest_run ? (
                                        <div style={{ display: "grid", gridTemplateColumns: "repeat(4, minmax(120px, 1fr))", gap: 10 }}>
                                            <div><div className="dim" style={{ fontSize: 11 }}>当前运行</div><div>{testStatus.latest_run.id}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>状态</div><div>{zhStatus(testStatus.latest_run.status)}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>总胜率</div><div>{fRate(testStatus.latest_run.summary.overall_win_rate ?? 0)}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>已完成</div><div>{testStatus.latest_run.summary.completed_matches ?? 0}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>进攻胜率</div><div>{fRate(testStatus.latest_run.summary.attack_win_rate ?? 0)}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>防守胜率</div><div>{fRate(testStatus.latest_run.summary.defense_win_rate ?? 0)}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>胜/平/负</div><div>{testStatus.latest_run.summary.wins ?? 0} / {testStatus.latest_run.summary.draws ?? 0} / {testStatus.latest_run.summary.losses ?? 0}</div></div>
                                            <div><div className="dim" style={{ fontSize: 11 }}>版本</div><div>bundle #{testStatus.latest_run.bundle_id}</div></div>
                                        </div>
                                    ) : (
                                        <div className="dim" style={{ fontSize: 12 }}>上传完进攻和防守模型后，会自动生成一版测试评测。</div>
                                    )}
                                </div>
                            </div>
                        )}

                        <div className="game-board-section">
                            <div className="sh">
                                {isTestPhase ? "测试榜单" : "排行榜"}
                                <span style={{ float: "right", fontWeight: "normal", textTransform: "none", letterSpacing: 0 }} className="dim">
                                    {isTestPhase
                                        ? (profile?.is_admin ? "管理员可见：按最新测试版本表现排序" : "测试阶段不显示正式排行榜")
                                        : "点击行 → 积分历史"}
                                </span>
                            </div>
                            <div className="tbl-wrap">
                                <table>
                                    <thead><tr>
                                        <th style={{ width: 28 }}>#</th>
                                        <th>用户</th>
                                        <th className="r">{isTestPhase ? "评分" : "score"}</th>
                                        <th className="r">胜</th>
                                        <th className="r">平</th>
                                        <th className="r">负</th>
                                        <th className="r">进攻%</th>
                                        <th className="r">防守%</th>
                                        {!isTestPhase && <th className="r">Δscore</th>}
                                    </tr></thead>
                                    <tbody>
                                        {board.length === 0
                                            ? <tr><td colSpan={isTestPhase ? 8 : 9} className="dim" style={{ padding: "6px 8px" }}>
                                                {isTestPhase && !profile?.is_admin ? "测试榜单仅管理员可见" : "暂无数据"}
                                            </td></tr>
                                            : board.map((row, i) => {
                                                const isSel = !isTestPhase && selected?.kind === "user" && selected.username === row.username;
                                                return (
                                                    <tr key={row.username}
                                                        className={isTestPhase ? undefined : `click${isSel ? " sel" : ""}`}
                                                        onClick={!isTestPhase ? () => setSelected(isSel ? null : { kind: "user", username: row.username }) : undefined}>
                                                        <td className="r dim">{i + 1}</td>
                                                        <td className="uname">{row.username}{row.is_agent && <span style={{ marginLeft: 4, fontSize: 12 }} title="AI Agent">🤖</span>}</td>
                                                        <td className="r">{fScore(row.score)}</td>
                                                        <td className="r pos">{row.wins}</td>
                                                        <td className="r dim">{row.draws}</td>
                                                        <td className="r neg">{row.losses}</td>
                                                        <td className="r">{fRate(row.attack_win_rate)}</td>
                                                        <td className="r">{fRate(row.defense_win_rate)}</td>
                                                        {!isTestPhase && <td className={`r ${row.score_delta >= 0 ? "pos" : "neg"}`}>{fDelta(row.score_delta)}</td>}
                                                    </tr>
                                                );
                                            })
                                        }
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="game-lower-section">
                            <div className="game-map-section">
                                <div className="sh">{hideRoundUiForPlayer ? `测试地图 (${maps.length})` : `地图 — round ${roundId} (${maps.length})`}
                                    <span style={{ float: "right", fontWeight: "normal", textTransform: "none", letterSpacing: 0 }} className="dim">
                                        点击行 → 预览
                                    </span>
                                </div>
                                <div className="tbl-wrap">
                                    <table>
                                        <thead><tr>
                                            <th className="r" style={{ width: 32 }}>#</th>
                                            <th>名称</th>
                                            <th className="r">障碍</th>
                                            <th className="r">包点A</th>
                                            <th className="r">包点B</th>
                                            <th className="r">T出生</th>
                                            <th className="r">CT出生</th>
                                        </tr></thead>
                                        <tbody>
                                            {maps.length === 0
                                                ? <tr><td colSpan={7} className="dim" style={{ padding: "6px 8px" }}>暂无地图</td></tr>
                                                : maps.map(m => {
                                                    const layout = m.layout as Record<string, unknown>;
                                                    const ml = (layout.map_layout ?? layout) as Record<string, unknown>;
                                                    const obs = (ml.obstacles as unknown[] | undefined)?.length ?? "?";
                                                    const siteA = ml.bomb_site_a ? (ml.bomb_site_a as number[]).join(",") : "?";
                                                    const siteB = ml.bomb_site_b ? (ml.bomb_site_b as number[]).join(",") : "?";
                                                    const tSp = ml.t_spawns ? (ml.t_spawns as number[][]).map(p => p.join(",")).join("/") : "?";
                                                    const ctSp = ml.ct_spawns ? (ml.ct_spawns as number[][]).map(p => p.join(",")).join("/") : "?";
                                                    const isSel = selected?.kind === "map" && selected.id === m.id;
                                                    return (
                                                        <tr key={m.id}
                                                            className={`click${isSel ? " sel" : ""}`}
                                                            onClick={() => setSelected(isSel ? null : { kind: "map", id: m.id })}>
                                                            <td className="r dim">{m.map_idx}</td>
                                                            <td><b>{m.name ?? m.slug ?? `map-${m.map_idx}`}</b></td>
                                                            <td className="r">{obs}</td>
                                                            <td className="r dim">{siteA}</td>
                                                            <td className="r dim">{siteB}</td>
                                                            <td className="r dim" style={{ fontSize: 10 }}>{tSp}</td>
                                                            <td className="r dim" style={{ fontSize: 10 }}>{ctSp}</td>
                                                        </tr>
                                                    );
                                                })
                                            }
                                        </tbody>
                                    </table>
                                </div>
                            </div>

                            <div className="game-match-section">
                                <MatchesTable
                                    roundId={roundId}
                                    hideRoundLabel={hideRoundUiForPlayer}
                                    roundOptions={sortedRounds}
                                    canPrevRound={canPrevRound}
                                    canNextRound={canNextRound}
                                    matches={visibleMatches}
                                    selectedMatchId={selected?.kind === "match" ? selected.id : null}
                                    isAdmin={Boolean(profile?.is_admin)}
                                    viewMode={effectiveMatchView}
                                    canUseSelfView={currentUserId != null && !forceGlobalMatchView}
                                    currentUserId={currentUserId}
                                    onChangeRoundId={nextRoundId => setRoundId(nextRoundId || DEFAULT_ROUND)}
                                    onPrevRound={() => {
                                        if (!canPrevRound) return;
                                        const next = sortedRounds[selectedRoundIndex + 1];
                                        if (next) setRoundId(next.id);
                                    }}
                                    onNextRound={() => {
                                        if (!canNextRound) return;
                                        const next = sortedRounds[selectedRoundIndex - 1];
                                        if (next) setRoundId(next.id);
                                    }}
                                    onChangeViewMode={changeMatchView}
                                    onSelectMatch={matchId => {
                                        if (matchId == null) {
                                            setSelected(null);
                                            return;
                                        }
                                        setSelected({ kind: "match", id: matchId });
                                    }}
                                    onRetryMatch={matchId => void doAdminAction(() => adminRetryMatch(matchId), `#${matchId} 重试`)}
                                    zhRole={zhRole}
                                    zhStatus={zhStatus}
                                    zhOutcome={zhOutcome}
                                    zhReason={zhReason}
                                />
                            </div>
                        </div>

                    </div>}

                </div>

                {/* ── Detail pane ── */}
                {selected && (<>
                    <div className="resize-handle" onPointerDown={onDetailResizeDown} />
                    <div className="detail" style={{ width: detailWidth, minWidth: detailWidth }}>
                        <div className="detail-head">
                            {selected.kind === "match"
                                ? <><span>对局 </span><b>#{selected.id}</b></>
                                : selected.kind === "user"
                                    ? <><span>用户 </span><b>{selected.username}</b></>
                                    : <><span>地图 </span><b>{maps.find(x => x.id === selected.id)?.name ?? `#${selected.id}`}</b></>
                            }
                            <button className="x" onClick={() => setSelected(null)}>✕</button>
                        </div>

                        {detailBusy && <div className="dim" style={{ padding: "8px 10px", fontSize: 11 }}>加载中…</div>}

                        {/* Match detail */}
                        {!detailBusy && selected.kind === "match" && matchDetail && (() => {
                            const r = matchDetail.result ?? {};
                            const reason = (r.reason as string | undefined) ?? "—";
                            const winner = (r.winner as string | undefined) ?? "—";
                            const steps = (r.steps as number | undefined) ?? "—";
                            const roleA = (r.team_a_role as string | undefined) ?? "—";
                            const roleB = (r.team_b_role as string | undefined) ?? "—";
                            const outA = (r.team_a_outcome as string | undefined) ?? "—";
                            const outB = (r.team_b_outcome as string | undefined) ?? "—";
                            const t1Dead = r.t1_alive === false;
                            const t2Dead = r.t2_alive === false;
                            const ct1Dead = r.ct1_alive === false;
                            const ct2Dead = r.ct2_alive === false;
                            const bombPlanted = r.bomb_planted as boolean | undefined;
                            const bombSite = r.bomb_site as number[] | undefined;
                            const teamAName = matchDetail.team_a_name || `队伍#${matchDetail.team_a_id}`;
                            const teamBName = matchDetail.team_b_name || (matchDetail.team_b_id != null ? `队伍#${matchDetail.team_b_id}` : "Baseline");
                            const teamAModel = matchDetail.team_a_model;
                            const teamBModel = matchDetail.team_b_model;
                            const isRoundMatch = "round_id" in matchDetail;
                            const matchMap = isRoundMatch
                                ? maps.find(x => x.id === matchDetail.map_id)
                                : maps.find(x => x.map_idx === matchDetail.map_idx);
                            const resolvedMapName = matchDetail.map_name ?? matchMap?.name;
                            const resolvedMapLabel = resolvedMapName ?? `map-${matchDetail.map_idx ?? (isRoundMatch ? matchDetail.map_id : "?")}`;
                            const bpTrace = r.bp_trace as { selected_maps?: { map_idx: number; name?: string }[] } | undefined;
                            return <>
                                <table className="kv">
                                    <tbody>
                                        <tr><td>状态</td><td className={`s-${matchDetail.status}`}>{zhStatus(matchDetail.status)}</td></tr>
                                        {!hideRoundUiForPlayer && isRoundMatch && <tr><td>轮次</td><td>第 {matchDetail.round_id} 轮</td></tr>}
                                        <tr><td>地图</td><td><b>{resolvedMapLabel}</b></td></tr>
                                        <tr><td>局次</td><td>{String(r.game_no ?? "—")}</td></tr>
                                        <tr><td>胜者</td><td><b>{zhWinner(winner)}</b></td></tr>
                                        <tr><td>原因</td><td>{zhReason(reason)}</td></tr>
                                        <tr><td>步数</td><td>{steps}</td></tr>
                                        <tr><td>队伍A</td><td><b>{teamAName}</b> <span className="dim">#{matchDetail.team_a_id} · {zhRole(roleA)} → {outA}</span></td></tr>
                                        <tr><td>队伍B</td><td><b>{teamBName}</b> <span className="dim">{matchDetail.team_b_id != null ? `#${matchDetail.team_b_id} · ` : ""}{zhRole(roleB)} → {outB}</span></td></tr>
                                        <tr>
                                            <td>模型A</td>
                                            <td>
                                                <span className="dim">{zhRole(teamAModel?.role ?? roleA)}</span>
                                                {teamAModel?.model_id
                                                    ? profile?.is_admin
                                                        ? (
                                                            <a
                                                                href="#"
                                                                onClick={evt => {
                                                                    evt.preventDefault();
                                                                    void downloadSubmission(teamAModel.model_id!).catch(err => setSubMsg({ ok: false, text: String(err instanceof Error ? err.message : err) }));
                                                                }}
                                                                style={{ marginLeft: 8, fontFamily: "ui-monospace,monospace", color: "var(--blue)", textDecoration: "underline" }}
                                                                title={`下载模型 ${teamAModel.model_id}`}
                                                            >
                                                                {modelIdLabel(teamAModel.model_id)}
                                                            </a>
                                                        )
                                                        : <code style={{ marginLeft: 8, color: "var(--blue)", fontSize: 11 }} title={teamAModel.model_id}>
                                                            {modelIdLabel(teamAModel.model_id)}
                                                        </code>
                                                    : <span style={{ marginLeft: 8, fontFamily: "ui-monospace,monospace" }}>—</span>}
                                            </td>
                                        </tr>
                                        <tr>
                                            <td>模型B</td>
                                            <td>
                                                <span className="dim">{zhRole(teamBModel?.role ?? roleB)}</span>
                                                {teamBModel?.model_id
                                                    ? profile?.is_admin
                                                        ? (
                                                            <a
                                                                href="#"
                                                                onClick={evt => {
                                                                    evt.preventDefault();
                                                                    void downloadSubmission(teamBModel.model_id!).catch(err => setSubMsg({ ok: false, text: String(err instanceof Error ? err.message : err) }));
                                                                }}
                                                                style={{ marginLeft: 8, fontFamily: "ui-monospace,monospace", color: "var(--blue)", textDecoration: "underline" }}
                                                                title={`下载模型 ${teamBModel.model_id}`}
                                                            >
                                                                {modelIdLabel(teamBModel.model_id)}
                                                            </a>
                                                        )
                                                        : <code style={{ marginLeft: 8, color: "var(--blue)", fontSize: 11 }} title={teamBModel.model_id}>
                                                            {modelIdLabel(teamBModel.model_id)}
                                                        </code>
                                                    : <span style={{ marginLeft: 8, fontFamily: "ui-monospace,monospace" }}>—</span>}
                                            </td>
                                        </tr>
                                        <tr><td>存活</td><td>
                                            <span style={{ color: t1Dead ? "var(--red)" : "var(--green)" }}>T1{t1Dead ? "✗" : "✓"}</span>{" "}
                                            <span style={{ color: t2Dead ? "var(--red)" : "var(--green)" }}>T2{t2Dead ? "✗" : "✓"}</span>{" "}
                                            <span style={{ color: ct1Dead ? "var(--red)" : "var(--green)" }}>CT1{ct1Dead ? "✗" : "✓"}</span>{" "}
                                            <span style={{ color: ct2Dead ? "var(--red)" : "var(--green)" }}>CT2{ct2Dead ? "✗" : "✓"}</span>
                                        </td></tr>
                                        {bombPlanted != null && <tr><td>炸弹</td><td>{bombPlanted ? `已安放 @ ${bombSite?.join(",") ?? "?"}` : "未安放"}</td></tr>}
                                        {bpTrace?.selected_maps && bpTrace.selected_maps.length > 0 && (
                                            <tr>
                                                <td>BP结果</td>
                                                <td>{bpTrace.selected_maps.map(item => `${item.map_idx}:${item.name ?? "?"}`).join(" / ")}</td>
                                            </tr>
                                        )}
                                    </tbody>
                                </table>
                                <div className="panel" style={{ marginTop: 8 }}>
                                    <div className="btns" style={{ marginTop: 0 }}>
                                        <button
                                            className="pri"
                                            disabled={matchDetail.status !== "completed"}
                                            onClick={() => setReplayOpen(true)}
                                        >
                                            打开Demo查看器
                                        </button>
                                        {replayBusy && <span className="dim" style={{ fontSize: 11 }}>加载中…</span>}
                                        {replayError && <span className="err" style={{ fontSize: 11 }}>{replayError}</span>}
                                    </div>
                                </div>
                            </>;
                        })()}

                        {/* User score history */}
                        {!detailBusy && selected.kind === "user" && (
                            <>
                                <div className="sh">{hideRoundUiForPlayer ? `测试表现 — ${selected.username}` : `积分历史 — ${selected.username}`}</div>
                                <table>
                                    <thead><tr>
                                        <th className="r">{hideRoundUiForPlayer ? "记录" : "轮次"}</th>
                                        <th className="r">前值</th>
                                        <th className="r">后值</th>
                                        <th className="r">Δ</th>
                                    </tr></thead>
                                    <tbody>
                                        {scoreHistory.length === 0
                                            ? <tr><td colSpan={4} className="dim" style={{ padding: "6px 8px" }}>暂无历史</td></tr>
                                            : scoreHistory.map((h, index) => (
                                                <tr key={h.round_id}>
                                                    <td className="r dim">{hideRoundUiForPlayer ? index + 1 : h.round_id}</td>
                                                    <td className="r">{fScore(h.score_before)}</td>
                                                    <td className="r">{fScore(h.score_after)}</td>
                                                    <td className={`r ${fDeltaClass(h.delta)}`}>{fDelta(h.delta)}</td>
                                                </tr>
                                            ))
                                        }
                                    </tbody>
                                </table>
                            </>
                        )}

                        {/* Map preview */}
                        {!detailBusy && selected.kind === "map" && (() => {
                            const m = maps.find(x => x.id === selected.id);
                            if (!m) return <div className="dim" style={{ padding: "8px 10px", fontSize: 11 }}>地图数据不存在</div>;
                            const layout = (m.layout as Record<string, unknown>);
                            const ml = (layout.map_layout ?? layout) as Record<string, unknown>;
                            const obs = (ml.obstacles as number[][] | undefined) ?? [];
                            const siteA = ml.bomb_site_a as number[] | undefined;
                            const siteB = ml.bomb_site_b as number[] | undefined;
                            const tSpawns = ml.t_spawns as number[][] | undefined;
                            const ctSpawns = ml.ct_spawns as number[][] | undefined;
                            return <>
                                <div className="panel" style={{ marginBottom: 8 }}>
                                    <div className="btns" style={{ marginTop: 0 }}>
                                        <button className="pri" onClick={() => void downloadVisibleMap(m)}>
                                            下载地图 .txt
                                        </button>
                                        <span className="dim" style={{ fontSize: 11 }}>
                                            可用于本地训练与回放复现
                                        </span>
                                    </div>
                                </div>
                                <table className="kv">
                                    <tbody>
                                        <tr><td>名称</td><td>{m.name ?? m.slug ?? `map-${m.map_idx}`}</td></tr>
                                        <tr><td>编号</td><td>{m.map_idx}</td></tr>
                                        <tr><td>障碍数</td><td>{obs.length}</td></tr>
                                        <tr><td>包点A</td><td>{siteA ? siteA.join(", ") : "—"}</td></tr>
                                        <tr><td>包点B</td><td>{siteB ? siteB.join(", ") : "—"}</td></tr>
                                        <tr><td>T出生</td><td>{tSpawns ? tSpawns.map(p => p.join(",")).join(" / ") : "—"}</td></tr>
                                        <tr><td>CT出生</td><td>{ctSpawns ? ctSpawns.map(p => p.join(",")).join(" / ") : "—"}</td></tr>
                                    </tbody>
                                </table>
                                <div className="sh" style={{ marginTop: 6, marginBottom: 4 }}>
                                    地图预览
                                    <span className="dim" style={{ fontWeight: "normal", textTransform: "none", letterSpacing: 0, marginLeft: 6 }}>
                                        <span style={{ color: "#f87171" }}>■</span> T &nbsp;
                                        <span style={{ color: "#60a5fa" }}>■</span> CT &nbsp;
                                        <span style={{ color: "#c8a800" }}>■</span> 包点 &nbsp;
                                        <span style={{ color: "#3d2810" }}>■</span> 障碍
                                    </span>
                                </div>
                                <GridCanvas
                                    obstacles={obs}
                                    bombSiteA={siteA}
                                    bombSiteB={siteB}
                                    t1Pos={tSpawns?.[0]}
                                    t2Pos={tSpawns?.[1]}
                                    ct1Pos={ctSpawns?.[0]}
                                    ct2Pos={ctSpawns?.[1]}
                                />
                            </>;
                        })()}
                    </div>
                </>)}

            </div>

            {/* ── Statusbar ── */}
            <div className="statusbar">
                <div className="statusbar-left">
                    {!hideRoundUiForPlayer && selectedRoundMeta && <>
                        <span className="tag">模式:<b>{selectedRoundMeta.created_mode === "auto" ? "自动" : "手动"}</b></span>
                        <span className="sep">│</span>
                    </>}
                    <span className="tag">
                        队列:<b>{lm?.queued ?? 0}</b>{" "}
                        进行:<b>{lm?.running ?? 0}</b>{" "}
                        完成:<b>{lm?.completed ?? 0}</b>{" "}
                        失败:<b style={lm?.failed ? { color: "var(--red)" } : {}}>{lm?.failed ?? 0}</b>
                    </span>
                    <span className="sep">│</span>
                    <span className="tag">地图:<b>{maps.length}</b></span>
                    <span className="sep">│</span>
                    <span className="tag">对局:<b>{matches.length}</b></span>
                </div>
                <div className="statusbar-right">
                    {sysHealth && <>
                        <span className="tag" title={`db:${sysHealth.db} redis:${sysHealth.redis} workers:${sysHealth.celery_workers}`}>
                            <span style={{ color: sysHealth.db && sysHealth.redis && sysHealth.celery_workers > 0 ? "var(--green)" : sysHealth.db ? "var(--yellow)" : "var(--red)" }}>
                                ● {sysHealth.celery_workers}w
                            </span>
                        </span>
                        <span className="sep">│</span>
                    </>}
                    <span className="tag" style={{ color: "var(--fg2)", fontSize: 11 }}
                        title={`前端: ${__APP_VERSION__}${svcStatus ? `  后端: ${svcStatus.version}` : ""}`}>
                        fe:{__APP_VERSION__}{svcStatus && <> · be:{svcStatus.version}</>}
                    </span>
                </div>
            </div>

            <HelpModal
                open={helpOpen}
                onClose={() => setHelpOpen(false)}
                profile={profile}
                siteConfig={siteCfg ?? registerStatus}
            />
            <ChangePasswordModal
                open={changePasswordOpen}
                onClose={() => setChangePasswordOpen(false)}
                currentPassword={currentPassword}
                newPassword={newPassword}
                confirmPassword={confirmPassword}
                onChangeCurrentPassword={setCurrentPassword}
                onChangeNewPassword={setNewPassword}
                onChangeConfirmPassword={setConfirmPassword}
                onSubmit={() => void doChangePassword()}
                busy={changePasswordBusy}
                message={changePasswordMsg}
            />
            <RegisterModal
                open={registerOpen}
                onClose={() => setRegisterOpen(false)}
                username={rUser}
                password={rPass}
                onChangeUsername={setRUser}
                onChangePassword={setRPass}
                onSubmit={() => void doRegister()}
                registerEnabled={Boolean(registerStatus?.allow_registration)}
                inviteToken={registerInviteToken}
                inviteStatus={inviteStatus}
                authMsg={authMsg}
            />
            <MapEditorModal
                open={mapEditorOpen}
                onClose={() => {
                    setMapEditorOpen(false);
                    setEditingMap(null);
                    setMapSaveMsg(null);
                }}
                map={editingMap}
                nextSortOrder={adminMaps.length}
                busy={mapSaveBusy}
                message={mapSaveMsg}
                onSave={draft => void saveAdminMap(draft)}
                onDownload={downloadAdminMap}
            />
            <ReplayModal
                open={replayOpen}
                onClose={() => setReplayOpen(false)}
                replayBusy={replayBusy}
                replayError={replayError}
                replayData={replayData}
                replayFrames={replayFrames}
                currentReplayFrame={currentReplayFrame}
                prevReplayFrame={prevReplayFrame}
                replayFrameIndex={replayFrameIndex}
                replayPlaying={replayPlaying}
                replaySpeedMs={replaySpeedMs}
                replayProgress={replayProgress}
                onTogglePlay={() => setReplayPlaying(p => !p)}
                onPrev={() => {
                    setReplayPlaying(false);
                    setReplayFrameIndex(i => Math.max(0, i - 1));
                }}
                onNext={() => {
                    setReplayPlaying(false);
                    setReplayFrameIndex(i => Math.min(replayFrames.length - 1, i + 1));
                }}
                onReset={() => {
                    setReplayPlaying(false);
                    setReplayFrameIndex(0);
                }}
                onSeek={index => {
                    setReplayPlaying(false);
                    setReplayFrameIndex(index);
                }}
                onSpeedChange={speed => setReplaySpeedMs(speed)}
                zhReplayPhase={zhReplayPhase}
                actionPairLabel={actionPairLabel}
            />

            <Modal
                open={agentTelemetryOpen}
                title={agentTelemetryDetail ? `🤖 Agent 遥测 — ${agentTelemetryDetail.username}` : "🤖 Agent 遥测"}
                onClose={() => setAgentTelemetryOpen(false)}
                position="center"
                size="large"
            >
                {agentTelemetryBusy && <div style={{ padding: "16px 20px", color: "var(--fg3)" }}>加载中…</div>}
                {agentTelemetryDetail && !agentTelemetryBusy && (
                    <div style={{ padding: "12px 16px" }}>
                        <div style={{ display: "flex", gap: 16, marginBottom: 12, flexWrap: "wrap" }}>
                            <span><span className="dim">Agent: </span><b>{agentTelemetryDetail.agent_name ?? "—"}</b></span>
                            <span><span className="dim">Model: </span><b>{agentTelemetryDetail.model_name ?? "—"}</b></span>
                            <span><span className="dim">记录数: </span><b>{agentTelemetryDetail.telemetry.length}</b></span>
                        </div>
                        {agentTelemetryDetail.telemetry.length === 0
                            ? <div className="dim">暂无遥测记录</div>
                            : <div style={{ overflowX: "auto" }}>
                                <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12 }}>
                                    <thead>
                                        <tr style={{ borderBottom: "1px solid var(--border)" }}>
                                            <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--fg3)", fontWeight: 500 }}>时间</th>
                                            <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--fg3)", fontWeight: 500 }}>Method</th>
                                            <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--fg3)", fontWeight: 500 }}>Path</th>
                                            <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--fg3)", fontWeight: 500 }}>Agent</th>
                                            <th style={{ textAlign: "left", padding: "4px 8px", color: "var(--fg3)", fontWeight: 500 }}>Model</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {agentTelemetryDetail.telemetry.map(r => (
                                            <tr key={r.id} style={{ borderBottom: "1px solid var(--border)" }}>
                                                <td style={{ padding: "3px 8px", color: "var(--fg3)", whiteSpace: "nowrap" }}>{fTime(r.recorded_at, true)}</td>
                                                <td style={{ padding: "3px 8px", color: "var(--cyan)", fontFamily: "monospace" }}>{r.method}</td>
                                                <td style={{ padding: "3px 8px", fontFamily: "monospace", maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{r.path}</td>
                                                <td style={{ padding: "3px 8px", color: "var(--fg2)" }}>{r.agent_name ?? "—"}</td>
                                                <td style={{ padding: "3px 8px", color: "var(--fg2)" }}>{r.model_name ?? "—"}</td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        }
                    </div>
                )}
            </Modal>

        </div>
    );
}
