export const fTime = (iso: string, sec = false) => {
    const d = new Date(/[Z+]/.test(iso) ? iso : iso + "Z");
    const pad = (n: number) => String(n).padStart(2, "0");
    const base = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    return sec ? base + `:${pad(d.getSeconds())}` : base;
};

export const fScore = (v: number) => v.toFixed(4);
