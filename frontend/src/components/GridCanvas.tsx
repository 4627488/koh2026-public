import { useEffect, useRef } from "react";

const GRID_SIZE = 25;
const CELL = 10;
const GAP = 1;
const STRIDE = CELL + GAP;
const CANVAS_SIZE = GRID_SIZE * STRIDE + GAP;

type GridCanvasProps = {
    obstacles?: number[][];
    bombSiteA?: number[];
    bombSiteB?: number[];
    plantedAt?: number[] | null;
    t1Pos?: number[] | null;
    t2Pos?: number[] | null;
    ct1Pos?: number[] | null;
    ct2Pos?: number[] | null;
    replayActions?: {
        t: [number, number] | null;
        ct: [number, number] | null;
    };
    cooldowns?: {
        t1: number;
        t2: number;
        ct1: number;
        ct2: number;
    };
    prevCooldowns?: {
        t1: number;
        t2: number;
        ct1: number;
        ct2: number;
    };
    showOverlay?: boolean;
};

export default function GridCanvas({
    obstacles = [],
    bombSiteA,
    bombSiteB,
    plantedAt,
    t1Pos,
    t2Pos,
    ct1Pos,
    ct2Pos,
    replayActions,
    cooldowns,
    prevCooldowns,
    showOverlay = false,
}: GridCanvasProps) {
    const ref = useRef<HTMLCanvasElement>(null);

    useEffect(() => {
        const canvas = ref.current;
        if (!canvas) return;
        const dpr = window.devicePixelRatio || 1;
        canvas.width = CANVAS_SIZE * dpr;
        canvas.height = CANVAS_SIZE * dpr;
        canvas.style.width = CANVAS_SIZE + "px";
        canvas.style.height = CANVAS_SIZE + "px";
        const ctx = canvas.getContext("2d")!;
        ctx.scale(dpr, dpr);

        ctx.fillStyle = "#1e1e1e";
        ctx.fillRect(0, 0, CANVAS_SIZE, CANVAS_SIZE);

        for (let r = 0; r < GRID_SIZE; r++) {
            for (let c = 0; c < GRID_SIZE; c++) {
                ctx.fillStyle = "#111";
                ctx.fillRect(GAP + c * STRIDE, GAP + r * STRIDE, CELL, CELL);
            }
        }

        const fill = (pos: number[], bg: string, fg?: string, label?: string) => {
            const [r, c] = pos;
            if (r < 0 || r >= GRID_SIZE || c < 0 || c >= GRID_SIZE) return;
            const x = GAP + c * STRIDE;
            const y = GAP + r * STRIDE;
            ctx.fillStyle = bg;
            ctx.fillRect(x, y, CELL, CELL);
            if (fg && label) {
                ctx.fillStyle = fg;
                ctx.font = `bold ${CELL - 2}px ui-monospace,monospace`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                ctx.fillText(label, x + CELL / 2, y + CELL / 2 + 0.5);
            }
        };

        const arrowFor = (a: number) => {
            if (a === 0) return "↑";
            if (a === 1) return "↓";
            if (a === 2) return "←";
            if (a === 3) return "→";
            return null;
        };

        const fireDelta = (a: number): [number, number] | null => {
            if (a === 5) return [-1, 0];
            if (a === 6) return [1, 0];
            if (a === 7) return [0, -1];
            if (a === 8) return [0, 1];
            return null;
        };

        const drawActionMark = (
            pos: number[] | null | undefined,
            action: number | null | undefined,
            color: string,
        ) => {
            if (!pos || action == null) return;
            const [r, c] = pos;
            const x = GAP + c * STRIDE;
            const y = GAP + r * STRIDE;
            const arr = arrowFor(action);
            if (arr) {
                ctx.fillStyle = color;
                ctx.font = `bold ${Math.max(8, CELL - 3)}px ui-monospace,monospace`;
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.fillText(arr, x + CELL / 2, y + 0.5);
            }
        };

        const obstacleSet = new Set(obstacles.map(([r, c]) => `${r},${c}`));

        const didFireEffectively = (
            action: number | null | undefined,
            currentCd: number | undefined,
            prevCd: number | undefined,
        ) => {
            if (action == null || action < 5 || action > 8) return false;
            if (currentCd == null || prevCd == null) return false;
            return currentCd > prevCd;
        };

        const drawFireRay = (
            pos: number[] | null | undefined,
            action: number | null | undefined,
            color: string,
            currentCd: number | undefined,
            prevCd: number | undefined,
        ) => {
            if (!pos || action == null) return;
            if (!didFireEffectively(action, currentCd, prevCd)) return;
            const d = fireDelta(action);
            if (!d) return;
            const [dr, dc] = d;
            let r = pos[0];
            let c = pos[1];
            const sx = GAP + c * STRIDE + CELL / 2;
            const sy = GAP + r * STRIDE + CELL / 2;
            let ex = sx;
            let ey = sy;
            for (let i = 0; i < 5; i++) {
                r += dr;
                c += dc;
                if (r < 0 || r >= GRID_SIZE || c < 0 || c >= GRID_SIZE) break;
                if (obstacleSet.has(`${r},${c}`)) break;
                ex = GAP + c * STRIDE + CELL / 2;
                ey = GAP + r * STRIDE + CELL / 2;
            }
            if (ex === sx && ey === sy) return;
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(ex, ey);
            ctx.stroke();
        };

        const drawCooldown = (
            pos: number[] | null | undefined,
            cd: number | undefined,
            color: string,
        ) => {
            if (!pos || cd == null || cd <= 0) return;
            const [r, c] = pos;
            const x = GAP + c * STRIDE;
            const y = GAP + r * STRIDE;
            ctx.fillStyle = "rgba(0,0,0,0.65)";
            ctx.fillRect(x + CELL - 5, y + CELL - 5, 5, 5);
            ctx.fillStyle = color;
            ctx.font = "bold 6px ui-monospace,monospace";
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillText(String(cd), x + CELL - 2.5, y + CELL - 2.5);
        };

        for (const pos of obstacles) fill(pos, "#3d2810");
        if (bombSiteA) fill(bombSiteA, "#2a2500", "#c8a800", "A");
        if (bombSiteB) fill(bombSiteB, "#2a2500", "#c8a800", "B");
        if (plantedAt) fill(plantedAt, "#5a0000", "#ff4040", "★");
        if (ct1Pos) fill(ct1Pos, "#0d2a5c", "#60a5fa", "3");
        if (ct2Pos) fill(ct2Pos, "#0d2a5c", "#93c5fd", "4");
        if (t1Pos) fill(t1Pos, "#5c0d0d", "#f87171", "1");
        if (t2Pos) fill(t2Pos, "#5c0d0d", "#fca5a5", "2");

        if (showOverlay) {
            const tA1 = replayActions?.t?.[0] ?? null;
            const tA2 = replayActions?.t?.[1] ?? null;
            const cA1 = replayActions?.ct?.[0] ?? null;
            const cA2 = replayActions?.ct?.[1] ?? null;

            drawFireRay(t1Pos, tA1, "rgba(248,113,113,0.8)", cooldowns?.t1, prevCooldowns?.t1);
            drawFireRay(t2Pos, tA2, "rgba(252,165,165,0.8)", cooldowns?.t2, prevCooldowns?.t2);
            drawFireRay(ct1Pos, cA1, "rgba(96,165,250,0.8)", cooldowns?.ct1, prevCooldowns?.ct1);
            drawFireRay(ct2Pos, cA2, "rgba(147,197,253,0.8)", cooldowns?.ct2, prevCooldowns?.ct2);

            drawActionMark(t1Pos, tA1, "#fecaca");
            drawActionMark(t2Pos, tA2, "#fee2e2");
            drawActionMark(ct1Pos, cA1, "#dbeafe");
            drawActionMark(ct2Pos, cA2, "#e0f2fe");

            drawCooldown(t1Pos, cooldowns?.t1, "#ffd1d1");
            drawCooldown(t2Pos, cooldowns?.t2, "#ffe4e4");
            drawCooldown(ct1Pos, cooldowns?.ct1, "#dbeafe");
            drawCooldown(ct2Pos, cooldowns?.ct2, "#e0f2fe");
        }
    }, [
        obstacles,
        bombSiteA,
        bombSiteB,
        plantedAt,
        t1Pos,
        t2Pos,
        ct1Pos,
        ct2Pos,
        replayActions,
        cooldowns,
        prevCooldowns,
        showOverlay,
    ]);

    return <canvas ref={ref} style={{ display: "block", imageRendering: "pixelated" }} />;
}
