import type { MatchRow } from "@/lib/api";

type MatchesTableProps = {
    roundId: number;
    hideRoundLabel?: boolean;
    roundOptions?: { id: number }[];
    canPrevRound?: boolean;
    canNextRound?: boolean;
    matches: MatchRow[];
    selectedMatchId: number | null;
    isAdmin: boolean;
    viewMode: "global" | "self";
    canUseSelfView: boolean;
    currentUserId: number | null;
    onChangeRoundId?: (roundId: number) => void;
    onPrevRound?: () => void;
    onNextRound?: () => void;
    onChangeViewMode: (mode: "global" | "self") => void;
    onSelectMatch: (matchId: number | null) => void;
    onRetryMatch: (matchId: number) => void;
    zhRole: (role: string) => string;
    zhStatus: (status: string) => string;
    zhOutcome: (outcome: string) => string;
    zhReason: (reason: string) => string;
};

/** Map winner string → which team id won, or "draw" / null (pending) */
function resolveWinner(
    row: MatchRow,
): "a" | "b" | "draw" | null {
    if (row.status !== "completed") return null;
    const r = row.result ?? {};
    const winner = (r.winner as string | undefined ?? "").toLowerCase();
    const roleA = (r.team_a_role as string | undefined ?? "attack").toLowerCase();
    if (winner === "draw") return "draw";
    if (winner === "attacker") return roleA === "attack" ? "a" : "b";
    if (winner === "defender") return roleA === "defense" ? "a" : "b";
    // fallback: check team_a_outcome
    const outcomeA = (r.team_a_outcome as string | undefined ?? "").toLowerCase();
    if (outcomeA === "win") return "a";
    if (outcomeA === "loss") return "b";
    if (outcomeA === "draw") return "draw";
    return null;
}

const ROLE_STYLE: Record<string, React.CSSProperties> = {
    attack: { color: "var(--red)", fontWeight: 600 },
    defense: { color: "var(--blue)", fontWeight: 600 },
};

function RoleBadge({ role, zh }: { role: string; zh: string }) {
    const style = ROLE_STYLE[role.toLowerCase()] ?? {};
    return <span style={style}>{zh}</span>;
}

const WIN_ROW_STYLE: React.CSSProperties = {
    borderLeft: "3px solid var(--green)",
};
const LOSS_ROW_STYLE: React.CSSProperties = {
    borderLeft: "3px solid var(--red)",
};
const DRAW_ROW_STYLE: React.CSSProperties = {
    borderLeft: "3px solid var(--yellow)",
};

function outcomeRowStyle(outcome: string | undefined, status: string): React.CSSProperties {
    if (status !== "completed") return { borderLeft: "3px solid transparent" };
    if (outcome === "win") return WIN_ROW_STYLE;
    if (outcome === "loss") return LOSS_ROW_STYLE;
    if (outcome === "draw") return DRAW_ROW_STYLE;
    return { borderLeft: "3px solid transparent" };
}

function winnerRowStyle(side: "a" | "b" | "draw" | null, perspective: "a" | "b"): React.CSSProperties {
    if (side === null) return { borderLeft: "3px solid transparent" };
    if (side === "draw") return DRAW_ROW_STYLE;
    return side === perspective ? WIN_ROW_STYLE : LOSS_ROW_STYLE;
}

export default function MatchesTable({
    roundId,
    hideRoundLabel = false,
    roundOptions = [],
    canPrevRound = false,
    canNextRound = false,
    matches,
    selectedMatchId,
    isAdmin,
    viewMode,
    canUseSelfView,
    currentUserId,
    onChangeRoundId,
    onPrevRound,
    onNextRound,
    onChangeViewMode,
    onSelectMatch,
    onRetryMatch,
    zhRole,
    zhStatus,
    zhOutcome,
    zhReason,
}: MatchesTableProps) {
    const isSelfView = viewMode === "self";

    return (
        <>
            <div className="sh">{hideRoundLabel ? `测试对局 (${matches.length})` : `历史对局 (${matches.length})`}
                <span style={{ float: "right", fontWeight: "normal", textTransform: "none", letterSpacing: 0 }} className="dim">
                    {!hideRoundLabel && (
                        <span style={{ marginRight: 10 }}>
                            <button
                                className="sm"
                                disabled={!canPrevRound}
                                style={{ marginRight: 4 }}
                                onClick={() => onPrevRound?.()}
                            >
                                ‹
                            </button>
                            <select
                                value={roundId}
                                onChange={e => onChangeRoundId?.(Number(e.target.value))}
                                style={{ marginRight: 4 }}
                            >
                                {(roundOptions.length === 0 || !roundOptions.some(r => r.id === roundId)) && <option value={roundId}>第{roundId}轮</option>}
                                {roundOptions.map(r => (
                                    <option key={r.id} value={r.id}>第{r.id}轮</option>
                                ))}
                            </select>
                            <button
                                className="sm"
                                disabled={!canNextRound}
                                style={{ marginRight: 6 }}
                                onClick={() => onNextRound?.()}
                            >
                                ›
                            </button>
                        </span>
                    )}
                    <span style={{ marginRight: 10 }}>
                        <button
                            className="sm"
                            style={{ marginRight: 6, opacity: !isSelfView ? 1 : 0.72 }}
                            onClick={() => onChangeViewMode("global")}
                        >
                            全局视角
                        </button>
                        <button
                            className="sm"
                            disabled={!canUseSelfView}
                            style={{ marginRight: 6, opacity: isSelfView ? 1 : 0.72 }}
                            onClick={() => onChangeViewMode("self")}
                        >
                            自己视角
                        </button>
                    </span>
                    点击行 → 详情
                </span>
            </div>
            <div className="tbl-wrap" style={{ flex: 1 }}>
                <table>
                    <thead><tr>
                        <th className="r" style={{ width: 44 }}>ID</th>
                        <th style={{ width: 80 }}>地图</th>
                        <th className="r" style={{ width: 44 }}>局次</th>
                        {isSelfView ? (
                            <>
                                <th>我方</th>
                                <th style={{ width: 50 }}>角色</th>
                                <th>对手</th>
                                <th style={{ width: 50 }}>角色</th>
                                <th style={{ width: 72 }}>结果</th>
                                <th>原因/状态</th>
                            </>
                        ) : (
                            <>
                                <th>队伍A</th>
                                <th style={{ width: 50 }}>角色</th>
                                <th>队伍B</th>
                                <th style={{ width: 50 }}>角色</th>
                                <th style={{ width: 80 }}>状态</th>
                                <th style={{ width: 80 }}>胜负</th>
                            </>
                        )}
                        <th className="r">步数</th>
                        {isAdmin && <th style={{ width: 36 }}></th>}
                    </tr></thead>
                    <tbody>
                        {matches.length === 0
                            ? <tr><td colSpan={isAdmin ? 11 : 10} className="dim" style={{ padding: "6px 8px" }}>暂无对局</td></tr>
                            : matches.map(row => {
                                const r = row.result ?? {};
                                const isSel = selectedMatchId === row.id;
                                const roleA = (r.team_a_role as string | undefined) ?? "—";
                                const roleB = (r.team_b_role as string | undefined) ?? "—";
                                const steps = r.steps as number | undefined;
                                const reason = (r.reason as string | undefined) ?? "—";
                                const teamAName = row.team_a_name || `队伍#${row.team_a_id}`;
                                const teamBName = row.team_b_name || (row.team_b_id != null ? `队伍#${row.team_b_id}` : "Baseline");

                                const winner = resolveWinner(row);

                                const isTeamA = currentUserId != null && row.team_a_id === currentUserId;
                                const myName = isTeamA ? teamAName : teamBName;
                                const myId = isTeamA ? row.team_a_id : row.team_b_id;
                                const myRole = isTeamA ? roleA : roleB;
                                const myOutcome = isTeamA
                                    ? (r.team_a_outcome as string | undefined)
                                    : (r.team_b_outcome as string | undefined);
                                const oppName = isTeamA ? teamBName : teamAName;
                                const oppId = isTeamA ? row.team_b_id : row.team_a_id;
                                const oppRole = isTeamA ? roleB : roleA;
                                const outcomeText = row.status === "completed"
                                    ? zhOutcome(myOutcome ?? "—")
                                    : zhStatus(row.status);

                                // Per-cell color helpers
                                const nameColorA = winner === null ? undefined
                                    : winner === "draw" ? "var(--yellow)"
                                    : winner === "a" ? "var(--green)"
                                    : "var(--fg3)";
                                const nameColorB = winner === null ? undefined
                                    : winner === "draw" ? "var(--yellow)"
                                    : winner === "b" ? "var(--green)"
                                    : "var(--fg3)";

                                const myPerspective = isTeamA ? "a" : "b";

                                return (
                                    <tr
                                        key={row.id}
                                        className={`click${isSel ? " sel" : ""}`}
                                        style={
                                            isSelfView
                                                ? outcomeRowStyle(myOutcome, row.status)
                                                : winnerRowStyle(winner, myPerspective)
                                        }
                                        onClick={() => onSelectMatch(isSel ? null : row.id)}
                                    >
                                        <td className="r dim">{row.id}</td>
                                        <td title={`map_id=${row.map_id}`}>{row.map_name ?? (row.map_idx != null ? `#${row.map_idx}` : row.map_id)}</td>
                                        <td className="r dim">{String(r.game_no ?? "—")}</td>
                                        {isSelfView ? (
                                            <>
                                                <td>
                                                    <span style={{
                                                        color: row.status === "completed"
                                                            ? myOutcome === "win" ? "var(--green)"
                                                            : myOutcome === "loss" ? "var(--red)"
                                                            : myOutcome === "draw" ? "var(--yellow)"
                                                            : undefined
                                                            : undefined,
                                                        fontWeight: row.status === "completed" && myOutcome === "win" ? 700 : undefined,
                                                    }}>
                                                        <b>{myName}</b>
                                                    </span>
                                                    {myId != null && <span className="dim" style={{ marginLeft: 6, fontSize: 11 }}>#{myId}</span>}
                                                </td>
                                                <td><RoleBadge role={myRole} zh={zhRole(myRole)} /></td>
                                                <td>
                                                    <span style={{
                                                        color: row.status === "completed"
                                                            ? myOutcome === "loss" ? "var(--green)"
                                                            : myOutcome === "win" ? "var(--red)"
                                                            : myOutcome === "draw" ? "var(--yellow)"
                                                            : undefined
                                                            : undefined,
                                                    }}>
                                                        <b>{oppName}</b>
                                                    </span>
                                                    {oppId != null && <span className="dim" style={{ marginLeft: 6, fontSize: 11 }}>#{oppId}</span>}
                                                </td>
                                                <td><RoleBadge role={oppRole} zh={zhRole(oppRole)} /></td>
                                                <td>
                                                    <OutcomeBadge outcome={myOutcome} status={row.status} text={outcomeText} />
                                                </td>
                                                <td className={`s-${row.status}`}>
                                                    {row.status === "completed" ? zhReason(reason) : zhStatus(row.status)}
                                                </td>
                                            </>
                                        ) : (
                                            <>
                                                <td>
                                                    <span style={{ color: nameColorA, fontWeight: winner === "a" ? 700 : undefined }}>
                                                        {teamAName}
                                                    </span>
                                                    {winner === "a" && <WinMark />}
                                                    <span className="dim" style={{ marginLeft: 4, fontSize: 11 }}>#{row.team_a_id}</span>
                                                </td>
                                                <td><RoleBadge role={roleA} zh={zhRole(roleA)} /></td>
                                                <td>
                                                    <span style={{ color: nameColorB, fontWeight: winner === "b" ? 700 : undefined }}>
                                                        {teamBName}
                                                    </span>
                                                    {winner === "b" && <WinMark />}
                                                    {row.team_b_id != null && <span className="dim" style={{ marginLeft: 4, fontSize: 11 }}>#{row.team_b_id}</span>}
                                                </td>
                                                <td><RoleBadge role={roleB} zh={zhRole(roleB)} /></td>
                                                <td className={`s-${row.status}`}>{zhStatus(row.status)}</td>
                                                <td>
                                                    <WinnerCell winner={winner} roleA={roleA} roleB={roleB} zhRole={zhRole} status={row.status} />
                                                </td>
                                            </>
                                        )}
                                        <td className="r dim">{steps ?? "—"}</td>
                                        {isAdmin && (
                                            <td onClick={e => e.stopPropagation()}>
                                                {(row.status === "failed" || row.status === "queued") && (
                                                    <button className="sm" style={{ color: "var(--yellow)" }} onClick={() => onRetryMatch(row.id)}>
                                                        ↺
                                                    </button>
                                                )}
                                            </td>
                                        )}
                                    </tr>
                                );
                            })}
                    </tbody>
                </table>
            </div>
        </>
    );
}

function WinMark() {
    return (
        <span style={{
            marginLeft: 4,
            fontSize: 10,
            color: "var(--green)",
            fontWeight: 700,
            letterSpacing: 0,
        }}>▲</span>
    );
}

function OutcomeBadge({ outcome, status, text }: { outcome: string | undefined; status: string; text: string }) {
    if (status !== "completed") {
        return <span className={`s-${status}`}>{text}</span>;
    }
    const style: React.CSSProperties =
        outcome === "win"
            ? { color: "var(--green)", fontWeight: 700 }
            : outcome === "loss"
            ? { color: "var(--red)" }
            : outcome === "draw"
            ? { color: "var(--yellow)" }
            : { color: "var(--fg3)" };
    return <span style={style}>{text}</span>;
}

function WinnerCell({
    winner,
    roleA,
    roleB,
    zhRole,
    status,
}: {
    winner: "a" | "b" | "draw" | null;
    roleA: string;
    roleB: string;
    zhRole: (r: string) => string;
    status: string;
}) {
    if (status !== "completed") return <span className="dim">—</span>;
    if (winner === null) return <span className="dim">—</span>;
    if (winner === "draw") return <span style={{ color: "var(--yellow)" }}>平局</span>;

    const winnerRole = winner === "a" ? roleA : roleB;
    const roleColor = winnerRole.toLowerCase() === "attack" ? "var(--red)" : "var(--blue)";
    return (
        <span style={{ color: "var(--green)", fontWeight: 700 }}>
            {winner === "a" ? "A" : "B"}
            <span style={{ color: roleColor, fontWeight: 400, marginLeft: 3, fontSize: 11 }}>
                {zhRole(winnerRole)}
            </span>
            <span style={{ color: "var(--green)", marginLeft: 3 }}>胜</span>
        </span>
    );
}
