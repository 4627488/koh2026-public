import type { ReplayData, ReplayFrame } from "@/lib/api";
import GridCanvas from "./GridCanvas";
import Modal from "./Modal";

type ReplayModalProps = {
    open: boolean;
    onClose: () => void;
    replayBusy: boolean;
    replayError: string | null;
    replayData: ReplayData | null;
    replayFrames: ReplayFrame[];
    currentReplayFrame: ReplayFrame | null;
    prevReplayFrame: ReplayFrame | null;
    replayFrameIndex: number;
    replayPlaying: boolean;
    replaySpeedMs: number;
    replayProgress: number;
    onTogglePlay: () => void;
    onPrev: () => void;
    onNext: () => void;
    onReset: () => void;
    onSeek: (index: number) => void;
    onSpeedChange: (speedMs: number) => void;
    zhReplayPhase: (phase: string) => string;
    actionPairLabel: (pair: [number, number] | null) => string;
};

export default function ReplayModal({
    open,
    onClose,
    replayBusy,
    replayError,
    replayData,
    replayFrames,
    currentReplayFrame,
    prevReplayFrame,
    replayFrameIndex,
    replayPlaying,
    replaySpeedMs,
    replayProgress,
    onTogglePlay,
    onPrev,
    onNext,
    onReset,
    onSeek,
    onSpeedChange,
    zhReplayPhase,
    actionPairLabel,
}: ReplayModalProps) {
    const progressPct = Math.round(replayProgress * 100);

    return (
        <Modal open={open} onClose={onClose} title="Demo 查看器" position="center" size="large">
            <div className="panel demo-viewer-shell">
                <div className="demo-viewer-head">
                    <span className="dim">逐帧查看攻守位置变化</span>
                    {!replayBusy && !replayError && currentReplayFrame && (
                        <>
                            <span className="demo-chip">帧 {replayFrameIndex + 1}/{replayFrames.length}</span>
                            <span className="demo-chip">step {currentReplayFrame.step}</span>
                            <span className="demo-chip">{zhReplayPhase(currentReplayFrame.phase)}</span>
                        </>
                    )}
                </div>

                {replayBusy && <div className="dim" style={{ padding: "8px 0", fontSize: 11 }}>回放加载中…</div>}
                {replayError && <div className="msg err">{replayError}</div>}
                {!replayBusy && !replayError && replayData && replayFrames.length > 0 && currentReplayFrame && <>
                    <div className="demo-viewer-body">
                        <div className="demo-viewer-canvas">
                            <GridCanvas
                                obstacles={replayData.layout.map_layout.obstacles}
                                bombSiteA={replayData.layout.map_layout.bomb_site_a}
                                bombSiteB={replayData.layout.map_layout.bomb_site_b}
                                plantedAt={currentReplayFrame.state.bomb_planted ? currentReplayFrame.state.bomb_site : null}
                                t1Pos={currentReplayFrame.state.t1_position}
                                t2Pos={currentReplayFrame.state.t2_position}
                                ct1Pos={currentReplayFrame.state.ct1_position}
                                ct2Pos={currentReplayFrame.state.ct2_position}
                                replayActions={{
                                    t: currentReplayFrame.t_actions,
                                    ct: currentReplayFrame.ct_actions,
                                }}
                                cooldowns={{
                                    t1: currentReplayFrame.state.t1_cooldown,
                                    t2: currentReplayFrame.state.t2_cooldown,
                                    ct1: currentReplayFrame.state.ct1_cooldown,
                                    ct2: currentReplayFrame.state.ct2_cooldown,
                                }}
                                prevCooldowns={prevReplayFrame ? {
                                    t1: prevReplayFrame.state.t1_cooldown,
                                    t2: prevReplayFrame.state.t2_cooldown,
                                    ct1: prevReplayFrame.state.ct1_cooldown,
                                    ct2: prevReplayFrame.state.ct2_cooldown,
                                } : undefined}
                                showOverlay
                            />

                            <div className="replay-meta" style={{ padding: 0, marginTop: 8 }}>
                                <span className="dim">叠加说明:</span>
                                <span className="dim">箭头=移动方向</span>
                                <span className="dim">细线=开火射线</span>
                                <span className="dim">角标数字=冷却剩余</span>
                            </div>
                        </div>

                        <div className="demo-viewer-side">
                            <div className="demo-viewer-card">
                                <div className="dim">动作</div>
                                <div className="demo-viewer-line">T: {actionPairLabel(currentReplayFrame.t_actions)}</div>
                                <div className="demo-viewer-line">CT: {actionPairLabel(currentReplayFrame.ct_actions)}</div>
                            </div>

                            <div className="demo-viewer-card">
                                <div className="dim">冷却</div>
                                <div className="demo-viewer-line">T: {currentReplayFrame.state.t1_cooldown}/{currentReplayFrame.state.t2_cooldown}</div>
                                <div className="demo-viewer-line">CT: {currentReplayFrame.state.ct1_cooldown}/{currentReplayFrame.state.ct2_cooldown}</div>
                            </div>

                            <div className="demo-viewer-card">
                                <div className="dim">回合状态</div>
                                {currentReplayFrame.state.bomb_planted && (
                                    <div className="demo-viewer-line" style={{ color: "var(--red)" }}>★ 倒计时 {currentReplayFrame.state.bomb_timer}</div>
                                )}
                                {!currentReplayFrame.state.bomb_planted && currentReplayFrame.state.plant_progress > 0 && (
                                    <div className="demo-viewer-line" style={{ color: "var(--yellow)" }}>下包中 {currentReplayFrame.state.plant_progress}/3</div>
                                )}
                                {currentReplayFrame.state.bomb_planted && currentReplayFrame.state.defuse_progress > 0 && (
                                    <div className="demo-viewer-line" style={{ color: "var(--blue)" }}>拆弹中 {currentReplayFrame.state.defuse_progress}/3</div>
                                )}
                                {!currentReplayFrame.state.bomb_planted && currentReplayFrame.state.plant_progress === 0 && (
                                    <div className="demo-viewer-line dim">炸弹未安放</div>
                                )}
                            </div>
                        </div>
                    </div>

                    <div className="replay-actions" style={{ padding: 0, marginTop: 8 }}>
                        <button className="sm pri" onClick={onTogglePlay}>{replayPlaying ? "暂停" : "播放"}</button>
                        <button className="sm" onClick={onPrev}>上一帧</button>
                        <button className="sm" onClick={onNext}>下一帧</button>
                        <button className="sm" onClick={onReset}>重置</button>
                        <span className="dim" style={{ marginLeft: "auto" }}>进度 {progressPct}%</span>
                    </div>

                    <input
                        className="replay-range"
                        type="range"
                        min={0}
                        max={Math.max(0, replayFrames.length - 1)}
                        value={replayFrameIndex}
                        onChange={e => onSeek(Number(e.target.value))}
                    />

                    <div className="replay-controls" style={{ padding: 0 }}>
                        <span className="dim">速度</span>
                        <select
                            value={replaySpeedMs}
                            onChange={e => onSpeedChange(Number(e.target.value) || 500)}
                            style={{
                                background: "var(--bg3)",
                                border: "1px solid var(--border)",
                                color: "var(--fg)",
                                fontFamily: "inherit",
                                fontSize: 12,
                                padding: "2px 4px",
                                flex: 1,
                            }}
                        >
                            <option value={800}>慢</option>
                            <option value={500}>标准</option>
                            <option value={250}>快</option>
                        </select>
                    </div>
                </>}
            </div>
        </Modal>
    );
}
