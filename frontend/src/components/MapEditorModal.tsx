import { useEffect, useMemo, useState } from "react";

import GridCanvas from "./GridCanvas";
import Modal from "./Modal";
import type { AdminMapTemplate } from "@/lib/api";

const GRID_SIZE = 25;
const TOOLS = [".", "#", "A", "B", "T", "C"] as const;
type Tool = typeof TOOLS[number];

type Draft = {
    name: string;
    source_text: string;
    sort_order: number;
    difficulty: number;
    is_active: boolean;
};

type Props = {
    open: boolean;
    map: AdminMapTemplate | null;
    nextSortOrder: number;
    busy: boolean;
    message: string | null;
    onClose: () => void;
    onSave: (draft: Draft) => void;
    onDownload?: (map: Pick<AdminMapTemplate, "name" | "slug" | "source_text">) => void;
};

function normalizeText(text: string) {
    const lines = text.replace(/\r\n/g, "\n").split("\n");
    while (lines.length > 0 && lines[0] === "") lines.shift();
    while (lines.length > 0 && lines[lines.length - 1] === "") lines.pop();
    return lines.join("\n");
}

function toGrid(text: string) {
    const lines = normalizeText(text).split("\n");
    const rows = Array.from({ length: GRID_SIZE }, (_, rowIdx) =>
        Array.from({ length: GRID_SIZE }, (_, colIdx) => lines[rowIdx]?.[colIdx] ?? "."),
    );
    return rows;
}

function fromGrid(grid: string[][]) {
    return grid.map(row => row.join("")).join("\n");
}

function parseLayout(sourceText: string) {
    const grid = toGrid(sourceText);
    const obstacles: number[][] = [];
    const tSpawns: number[][] = [];
    const ctSpawns: number[][] = [];
    let bombSiteA: number[] | undefined;
    let bombSiteB: number[] | undefined;

    for (let row = 0; row < GRID_SIZE; row += 1) {
        for (let col = 0; col < GRID_SIZE; col += 1) {
            const cell = grid[row][col];
            if (cell === "#") obstacles.push([row, col]);
            if (cell === "T") tSpawns.push([row, col]);
            if (cell === "C") ctSpawns.push([row, col]);
            if (cell === "A") bombSiteA = [row, col];
            if (cell === "B") bombSiteB = [row, col];
        }
    }

    const errors: string[] = [];
    if (tSpawns.length !== 2) errors.push(`T 出生点需要 2 个，当前 ${tSpawns.length}`);
    if (ctSpawns.length !== 2) errors.push(`CT 出生点需要 2 个，当前 ${ctSpawns.length}`);
    if (!bombSiteA) errors.push("缺少包点 A");
    if (!bombSiteB) errors.push("缺少包点 B");

    return {
        grid,
        obstacles,
        bombSiteA,
        bombSiteB,
        tSpawns,
        ctSpawns,
        errors,
    };
}

function cellClass(cell: string) {
    if (cell === ".") return "cell-empty";
    if (cell === "#") return "cell-wall";
    return `cell-${cell.toLowerCase()}`;
}

export default function MapEditorModal({
    open,
    map,
    nextSortOrder,
    busy,
    message,
    onClose,
    onSave,
    onDownload,
}: Props) {
    const [name, setName] = useState("");
    const [sourceText, setSourceText] = useState("");
    const [sortOrder, setSortOrder] = useState(nextSortOrder);
    const [difficulty, setDifficulty] = useState(0.5);
    const [isActive, setIsActive] = useState(true);
    const [tool, setTool] = useState<Tool>("#");

    useEffect(() => {
        if (!open) return;
        setName(map?.name ?? "");
        setSourceText(map?.source_text ?? Array.from({ length: GRID_SIZE }, () => ".".repeat(GRID_SIZE)).join("\n"));
        setSortOrder(map?.sort_order ?? nextSortOrder);
        setDifficulty(map?.difficulty ?? 0.5);
        setIsActive(map?.is_active ?? true);
        setTool("#");
    }, [open, map, nextSortOrder]);

    const parsed = useMemo(() => parseLayout(sourceText), [sourceText]);

    function applyTool(row: number, col: number) {
        const next = parsed.grid.map(line => [...line]);
        for (let r = 0; r < GRID_SIZE; r += 1) {
            for (let c = 0; c < GRID_SIZE; c += 1) {
                if (tool === "A" && next[r][c] === "A") next[r][c] = ".";
                if (tool === "B" && next[r][c] === "B") next[r][c] = ".";
                if (tool === "T" && next[r][c] === "T" && !(r === row && c === col)) {
                    const currentCount = next.flat().filter(cell => cell === "T").length;
                    if (currentCount >= 2) {
                        next[r][c] = ".";
                        break;
                    }
                }
                if (tool === "C" && next[r][c] === "C" && !(r === row && c === col)) {
                    const currentCount = next.flat().filter(cell => cell === "C").length;
                    if (currentCount >= 2) {
                        next[r][c] = ".";
                        break;
                    }
                }
            }
        }
        if ((tool === "T" || tool === "C") && next[row][col] === tool) {
            next[row][col] = ".";
        } else {
            next[row][col] = tool;
        }
        setSourceText(fromGrid(next));
    }

    return (
        <Modal open={open} onClose={onClose} title={map ? `编辑地图 #${map.id}` : "新建地图"} size="large">
            <div style={{ padding: 12, display: "grid", gridTemplateColumns: "340px 1fr", gap: 12 }}>
                <div>
                    <div className="fr">
                        <label>名称</label>
                        <input type="text" value={name} onChange={e => setName(e.target.value)} />
                    </div>
                    <div className="fr">
                        <label>排序</label>
                        <input type="number" value={sortOrder} onChange={e => setSortOrder(Number(e.target.value) || 0)} />
                    </div>
                    <div className="fr">
                        <label>难度</label>
                        <input
                            type="number"
                            min={0}
                            max={1}
                            step={0.05}
                            value={difficulty}
                            onChange={e => setDifficulty(Math.max(0, Math.min(1, Number(e.target.value) || 0)))}
                        />
                    </div>
                    <div className="fr" style={{ justifyContent: "space-between" }}>
                        <label>启用</label>
                        <input type="checkbox" checked={isActive} onChange={e => setIsActive(e.target.checked)} />
                    </div>
                    <div className="dim" style={{ fontSize: 11, marginBottom: 6 }}>点击网格直接绘制，右侧文本会同步更新。</div>
                    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 8 }}>
                        {TOOLS.map(item => (
                            <button
                                key={item}
                                className={`sm${tool === item ? " pri" : ""}`}
                                onClick={() => setTool(item)}
                            >
                                {item === "." ? "清空" : item}
                            </button>
                        ))}
                    </div>
                    <div className="map-edit-grid">
                        {parsed.grid.map((row, rowIdx) =>
                            row.map((cell, colIdx) => (
                                <button
                                    key={`${rowIdx}-${colIdx}`}
                                    type="button"
                                    className={`map-edit-cell ${cellClass(cell)}`}
                                    onClick={() => applyTool(rowIdx, colIdx)}
                                >
                                    {cell === "." ? "" : cell}
                                </button>
                            )),
                        )}
                    </div>
                </div>
                <div>
                    <textarea
                        value={sourceText}
                        onChange={e => setSourceText(e.target.value)}
                        style={{
                            width: "100%",
                            minHeight: 340,
                            resize: "vertical",
                            background: "var(--bg3)",
                            border: "1px solid var(--border)",
                            color: "var(--fg)",
                            padding: 8,
                            fontFamily: "inherit",
                            fontSize: 12,
                            lineHeight: 1.2,
                        }}
                    />
                    <div style={{ display: "flex", gap: 12, marginTop: 8, alignItems: "flex-start" }}>
                        <div>
                            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>实时预览</div>
                            <GridCanvas
                                obstacles={parsed.obstacles}
                                bombSiteA={parsed.bombSiteA}
                                bombSiteB={parsed.bombSiteB}
                                t1Pos={parsed.tSpawns[0]}
                                t2Pos={parsed.tSpawns[1]}
                                ct1Pos={parsed.ctSpawns[0]}
                                ct2Pos={parsed.ctSpawns[1]}
                            />
                        </div>
                        <div style={{ flex: 1 }}>
                            <div className="dim" style={{ fontSize: 11, marginBottom: 4 }}>校验</div>
                            {parsed.errors.length === 0
                                ? <div className="pos" style={{ fontSize: 12 }}>格式通过</div>
                                : parsed.errors.map(error => <div key={error} className="neg" style={{ fontSize: 12 }}>{error}</div>)}
                            {message && (
                                <div className="dim" style={{ marginTop: 8, fontSize: 12 }}>{message}</div>
                            )}
                            <div className="btns" style={{ marginTop: 12 }}>
                                {map && onDownload && (
                                    <button
                                        type="button"
                                        onClick={() => onDownload({
                                            name: map.name,
                                            slug: map.slug,
                                            source_text: sourceText,
                                        })}
                                    >
                                        下载 .txt
                                    </button>
                                )}
                                <button className="pri" disabled={busy} onClick={() => onSave({
                                    name,
                                    source_text: sourceText,
                                    sort_order: sortOrder,
                                    difficulty,
                                    is_active: isActive,
                                })}>
                                    {busy ? "保存中…" : "保存地图"}
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </Modal>
    );
}
