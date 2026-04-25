export type ApiResult<T> = { ok: boolean; data: T };

export class ApiError extends Error {
    status: number;

    constructor(message: string, status: number) {
        super(message);
        this.name = "ApiError";
        this.status = status;
    }
}

export type UserProfile = {
    id: number;
    username: string;
    display_name: string;
    is_admin: boolean;
    score: number;
};

export type InviteStatus = {
    token: string;
    valid: boolean;
    revoked: boolean;
    max_uses: number;
    used_count: number;
    remaining_uses: number;
    created_by_user_id: number | null;
    created_at: string | null;
    updated_at: string | null;
};

export type LeaderboardRow = {
    username: string;
    score: number;
    is_agent: boolean;
    wins: number;
    draws: number;
    losses: number;
    attack_win_rate: number;
    defense_win_rate: number;
    score_delta: number;
};

export type LeaderboardResult = {
    rows: LeaderboardRow[];
    phase: string;
};

export type MatchRow = {
    id: number;
    round_id: number;
    map_id: number;
    map_idx?: number | null;
    map_name?: string | null;
    team_a_id: number;
    team_a_name?: string | null;
    team_b_id: number | null;
    team_b_name?: string | null;
    status: string;
    result: Record<string, unknown>;
    team_a_model?: {
        role: string;
        model_id: string | null;
    };
    team_b_model?: {
        role: string;
        model_id: string | null;
    };
};

export type RoundMap = {
    id: number;
    round_id: number;
    template_id?: number | null;
    name?: string;
    slug?: string;
    map_idx: number;
    seed: string;
    difficulty?: number;
    layout: Record<string, unknown>;
};

export type RoundSummary = {
    id: number;
    status: string;
    created_mode: string;
    created_at: string;
};

export type RoundLivePayload = {
    round_id: number;
    round_exists: boolean;
    round_status: string;
    matches: {
        total: number;
        queued: number;
        running: number;
        completed: number;
        failed: number;
    };
    error?: string;
};

export type ReplayFrame = {
    step: number;
    phase: string;
    t_actions: [number, number] | null;
    ct_actions: [number, number] | null;
    state: {
        step: number;
        t1_position: number[] | null;
        t2_position: number[] | null;
        ct1_position: number[] | null;
        ct2_position: number[] | null;
        t1_alive: boolean;
        t2_alive: boolean;
        ct1_alive: boolean;
        ct2_alive: boolean;
        t1_cooldown: number;
        t2_cooldown: number;
        ct1_cooldown: number;
        ct2_cooldown: number;
        bomb_planted: boolean;
        bomb_site: number[] | null;
        bomb_timer: number;
        plant_progress: number;
        defuse_progress: number;
    };
    result: Record<string, unknown> | null;
};

export type ReplayMapLayout = {
    name: string;
    grid_size: number;
    t_spawns: number[][];
    ct_spawns: number[][];
    bomb_site_a: number[];
    bomb_site_b: number[];
    obstacles: number[][];
};

export type ReplayData = {
    layout: {
        round_id: number;
        map_layout: ReplayMapLayout;
    };
    max_steps: number;
    frames: ReplayFrame[];
    result: Record<string, unknown>;
};

export type ScoreHistoryRow = {
    round_id: number;
    score_before: number;
    score_after: number;
    delta: number;
};

export type BPData = {
    map_preferences: number[];
} | null;

export type ServiceStatus = {
    service: string;
    version: string;
    phase: string;
    current_round_id: number | null;
    next_round_id: number | null;
    next_round_at: string | null;
    auto_round_enabled: boolean;
    auto_round_state: string;
    competition_starts_at: string | null;
    competition_ends_at: string | null;
    round_interval_minutes: number;
    maps: number;
    latest_test_run_id?: number | null;
};

export type TestBundle = {
    id: number;
    user_id: number;
    attack_submission_id: number;
    defense_submission_id: number;
    map_preferences: number[];
    created_at: string;
};

export type TestRunSummary = {
    wins?: number;
    draws?: number;
    losses?: number;
    attack_games?: number;
    attack_wins?: number;
    defense_games?: number;
    defense_wins?: number;
    completed_matches?: number;
    failed_matches?: number;
    pending_matches?: number;
    attack_win_rate?: number;
    defense_win_rate?: number;
    overall_win_rate?: number;
    baseline_results?: Array<{
        baseline_id: number | null;
        baseline_display_name: string;
        wins: number;
        draws: number;
        losses: number;
        matches: number;
    }>;
};

export type TestRun = {
    id: number;
    bundle_id: number;
    user_id: number;
    baseline_pack_version: string;
    status: string;
    summary: TestRunSummary;
    queued_at: string;
    started_at: string | null;
    finished_at: string | null;
};

export type TestStatus = {
    phase: string;
    has_bundle: boolean;
    latest_bundle: TestBundle | null;
    latest_run: TestRun | null;
};

export type TestMatchRow = {
    id: number;
    test_run_id: number;
    contestant_user_id: number;
    baseline_id: number | null;
    team_a_id: number;
    team_a_name?: string | null;
    team_b_id: number | null;
    team_b_name?: string | null;
    map_template_id?: number | null;
    map_idx: number;
    map_name: string;
    status: string;
    result: Record<string, unknown>;
    team_a_model?: {
        role: string;
        model_id: string | null;
    };
    team_b_model?: {
        role: string;
        model_id: string | null;
    };
};

export type TestRunLivePayload = {
    test_run_id: number;
    test_run_exists: boolean;
    test_run_status: string;
    matches: {
        total: number;
        queued: number;
        running: number;
        completed: number;
        failed: number;
    };
    summary: TestRunSummary;
    error?: string;
};

const tokenStoreKey = "koh_token";

export function getToken() {
    return localStorage.getItem(tokenStoreKey) ?? "";
}

export function setToken(token: string) {
    if (token) {
        localStorage.setItem(tokenStoreKey, token);
    } else {
        localStorage.removeItem(tokenStoreKey);
    }
}

function withAuth(headers: HeadersInit = {}): HeadersInit {
    const token = getToken();
    if (!token) return headers;
    return { ...headers, Authorization: `Bearer ${token}` };
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await fetch(path, {
        cache: "no-store",
        ...init,
        headers: withAuth(init.headers),
    });
    const payload = (await response.json().catch(() => ({ ok: false }))) as ApiResult<T> & {
        detail?: string;
    };
    if (!response.ok || !payload.ok) {
        throw new ApiError(payload.detail || `HTTP ${response.status}`, response.status);
    }
    return payload.data;
}

export async function login(username: string, password: string) {
    return api<{ token: string; expires_at: string }>("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
    });
}

export async function register(username: string, password: string, invite_token?: string) {
    return api<{ username: string }>("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password, invite_token: invite_token || undefined }),
    });
}

export async function getRegisterStatus() {
    return api<SiteConfig>("/api/auth/register-status");
}

export async function getInviteStatus(token: string) {
    return api<InviteStatus>(`/api/auth/invite-status?token=${encodeURIComponent(token)}`);
}

export async function me() {
    return api<UserProfile>("/api/auth/me");
}

export async function changePassword(current_password: string, new_password: string) {
    return api<{ token: string; expires_at: string }>("/api/auth/change-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ current_password, new_password }),
    });
}

export async function getLeaderboard() {
    return api<LeaderboardResult>("/api/leaderboard");
}

export async function getPublicLeaderboard() {
    return api<LeaderboardResult>("/api/public/leaderboard");
}

export async function getRoundMaps(roundId: number) {
    return api<RoundMap[]>(`/api/rounds/${roundId}/maps`);
}

export async function getRounds(limit = 50) {
    return api<RoundSummary[]>(`/api/rounds?limit=${Math.max(1, Math.min(limit, 200))}`);
}

export async function getRoundMatches(roundId: number) {
    return api<MatchRow[]>(`/api/rounds/${roundId}/matches`);
}

export async function downloadRoundMap(roundId: number, mapId: number, fallbackName: string) {
    const res = await fetch(`/api/rounds/${roundId}/maps/${mapId}/download`, {
        method: "GET",
        headers: withAuth(),
        cache: "no-store",
    });
    if (!res.ok) {
        const payload = await res.json().catch(() => ({ detail: `HTTP ${res.status}` })) as { detail?: string };
        throw new Error(payload.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const filename = parseFilenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}

export async function downloadTestMap(mapId: number, fallbackName: string) {
    const res = await fetch(`/api/test/maps/${mapId}/download`, {
        method: "GET",
        headers: withAuth(),
        cache: "no-store",
    });
    if (!res.ok) {
        const payload = await res.json().catch(() => ({ detail: `HTTP ${res.status}` })) as { detail?: string };
        throw new Error(payload.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const filename = parseFilenameFromDisposition(res.headers.get("Content-Disposition"), fallbackName);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}

export async function upsertBp(payload: { map_preferences: number[] }) {
    return api<{ saved: boolean }>(`/api/bp`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function getBp() {
    return api<BPData>(`/api/bp`);
}

export async function getMatch(matchId: number) {
    return api<MatchRow>(`/api/matches/${matchId}`);
}

export async function getMatchReplay(matchId: number) {
    return api<ReplayData>(`/api/matches/${matchId}/replay`);
}

export async function getScoreHistory(username: string) {
    return api<ScoreHistoryRow[]>(`/api/users/${username}/score-history`);
}

export async function getPublicScoreHistory(username: string) {
    return api<ScoreHistoryRow[]>(`/api/public/users/${encodeURIComponent(username)}/score-history`);
}

export async function getStatus() {
    return api<ServiceStatus>("/api/status");
}

export async function getTestStatus() {
    return api<TestStatus>("/api/test/status");
}

export async function getTestMaps() {
    return api<RoundMap[]>("/api/test/maps");
}

export async function getTestBundles(limit = 20) {
    return api<TestBundle[]>(`/api/test/bundles?limit=${Math.max(1, Math.min(limit, 100))}`);
}

export async function getTestBundle(bundleId: number) {
    return api<{ bundle: TestBundle; runs: TestRun[] }>(`/api/test/bundles/${bundleId}`);
}

export async function getTestRun(runId: number) {
    return api<TestRun>(`/api/test/runs/${runId}`);
}

export async function getTestRuns(limit = 50, userId?: number) {
    const qs = new URLSearchParams();
    qs.set("limit", String(Math.max(1, Math.min(limit, 200))));
    if (userId != null) qs.set("user_id", String(userId));
    return api<TestRun[]>(`/api/test/runs?${qs.toString()}`);
}

export async function getTestRunMatches(runId: number) {
    return api<TestMatchRow[]>(`/api/test/runs/${runId}/matches`);
}

export async function getTestMatches(limit = 200, userId?: number) {
    const qs = new URLSearchParams();
    qs.set("limit", String(Math.max(1, Math.min(limit, 1000))));
    if (userId != null) qs.set("user_id", String(userId));
    return api<TestMatchRow[]>(`/api/test/matches?${qs.toString()}`);
}

export async function getTestMatch(matchId: number) {
    return api<TestMatchRow>(`/api/test/matches/${matchId}`);
}

export async function getTestMatchReplay(matchId: number) {
    return api<ReplayData>(`/api/test/matches/${matchId}/replay`);
}

// ── submissions ───────────────────────────────────────────────

export type SubmissionRow = {
    id: string | null;
    role: string;
    round_id?: number;
    uploaded_at: string;
    inherited?: boolean;
};

export async function uploadSubmission(role: string, file: File) {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    form.append("role", role);
    form.append("file", file);
    const res = await fetch(`/api/submissions`, {
        method: "POST", headers, body: form, cache: "no-store",
    });
    const payload = await res.json().catch(() => ({ ok: false })) as ApiResult<SubmissionRow> & { detail?: string };
    if (!res.ok || !payload.ok) throw new Error(payload.detail || `HTTP ${res.status}`);
    return payload.data;
}

export async function getSubmissions(roundId: number) {
    return api<SubmissionRow[]>(`/api/rounds/${roundId}/submissions`);
}

export async function getAllSubmissions() {
    return api<SubmissionRow[]>(`/api/submissions`);
}

function parseFilenameFromDisposition(disposition: string | null, fallback: string) {
    if (!disposition) return fallback;
    const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
    if (utf8Match?.[1]) {
        try {
            return decodeURIComponent(utf8Match[1]);
        } catch {
            return utf8Match[1];
        }
    }
    const plainMatch = disposition.match(/filename=\"?([^\";]+)\"?/i);
    return plainMatch?.[1] || fallback;
}

export async function downloadSubmission(modelId: string) {
    const res = await fetch(`/api/submissions/${encodeURIComponent(modelId)}/download`, {
        method: "GET",
        headers: withAuth(),
        cache: "no-store",
    });
    if (!res.ok) {
        const payload = await res.json().catch(() => ({ detail: `HTTP ${res.status}` })) as { detail?: string };
        throw new Error(payload.detail || `HTTP ${res.status}`);
    }
    const blob = await res.blob();
    const fallback = `model-${modelId.slice(0, 8)}.safetensors`;
    const filename = parseFilenameFromDisposition(res.headers.get("Content-Disposition"), fallback);
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
}

// ── admin ─────────────────────────────────────────────────────

export type AdminRound = {
    id: number;
    status: string;
    created_mode: string;
    created_at: string;
};

export type AdminUser = {
    id: number;
    username: string;
    display_name: string;
    login_username: string;
    is_admin: boolean;
    is_active: boolean;
    is_agent: boolean;
    is_spectator: boolean;
    agent_name: string | null;
    model_name: string | null;
    score: number;
    created_at: string;
};

export type ImportUserRow = {
    line: number;
    team_name: string;
    username: string;
    display_name: string;
    password: string;
};

export type ImportErrorRow = {
    line: number;
    team_name?: string;
    username?: string;
    error: string;
};

export type ImportUsersResult = {
    created_count: number;
    error_count: number;
    blank_lines: number;
    dry_run: boolean;
    created: ImportUserRow[];
    errors: ImportErrorRow[];
};

export type AdminBaseline = {
    id: number;
    display_name: string;
    attack_submission_id: number;
    defense_submission_id: number;
    is_active: boolean;
    sort_order: number;
    created_at: string;
    updated_at: string;
};

export type AdminSubmission = {
    id: number;
    user_id: number;
    username: string;
    role: string;
    file_hash: string | null;
    uploaded_at: string;
};

export type AgentTelemetryRow = {
    id: number;
    agent_name: string | null;
    model_name: string | null;
    method: string;
    path: string;
    recorded_at: string;
};

export type AgentTelemetryDetail = {
    user_id: number;
    username: string;
    is_agent: boolean;
    agent_name: string | null;
    model_name: string | null;
    telemetry: AgentTelemetryRow[];
};

export async function adminListRounds() {
    return api<AdminRound[]>("/api/admin/rounds");
}

export async function adminCreateRound(auto_run = false) {
    return api<AdminRound>("/api/admin/rounds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ auto_run }),
    });
}

export async function adminDeleteRound(roundId: number) {
    return api<{ deleted_round_id: number }>(`/api/admin/rounds/${roundId}`, { method: "DELETE" });
}

export async function adminPipelineRound(roundId: number) {
    return api<{ round_id: number; task: string; close_in_seconds: number }>(`/api/admin/rounds/${roundId}/pipeline`, { method: "POST" });
}

export async function adminFinalizeRound(roundId: number) {
    return api<{ round_id: number; task: string }>(`/api/admin/rounds/${roundId}/finalize`, { method: "POST" });
}

export async function adminRerunRound(roundId: number) {
    return api<{ round_id: number; task: string; deleted_matches: number }>(`/api/admin/rounds/${roundId}/rerun`, { method: "POST" });
}

export async function adminListUsers() {
    return api<AdminUser[]>("/api/admin/users");
}

export async function adminToggleActive(userId: number) {
    return api<{ id: number; is_active: boolean }>(`/api/admin/users/${userId}/toggle-active`, { method: "POST" });
}

export async function adminToggleAdmin(userId: number) {
    return api<{ id: number; is_admin: boolean }>(`/api/admin/users/${userId}/toggle-admin`, { method: "POST" });
}

export async function adminToggleSpectator(userId: number) {
    return api<{ id: number; is_spectator: boolean }>(`/api/admin/users/${userId}/toggle-spectator`, { method: "POST" });
}

export async function adminResetScore(userId: number) {
    return api<{ id: number; score: number }>(`/api/admin/users/${userId}/reset-score`, { method: "POST" });
}

export async function adminResetPassword(userId: number) {
    return api<{ id: number; username: string; password: string }>(`/api/admin/users/${userId}/reset-password`, { method: "POST" });
}

export async function adminGetAgentTelemetry(userId: number, limit = 200) {
    return api<AgentTelemetryDetail>(`/api/admin/users/${userId}/agent-telemetry?limit=${limit}`);
}

export type SystemHealth = {
    db: boolean;
    redis: boolean;
    celery_workers: number;
    celery_active_tasks: number;
};

export type RoundOverviewUser = {
    user_id: number;
    username: string;
    has_attack_sub: boolean;
    has_defense_sub: boolean;
    has_bp: boolean;
    matches_total: number;
    matches_queued: number;
    matches_running: number;
    matches_completed: number;
    matches_failed: number;
};

export type AdminAllSubmission = {
    id: number;
    user_id: number;
    username: string;
    role: string;
    uploaded_at: string;
};

export type AutoRoundConfig = {
    enabled: boolean;
    interval_minutes: number;
    competition_starts_at: string | null;
    competition_ends_at: string | null;
    schedule_state: string;
    next_slot_at: string | null;
    updated_at: string;
    env_defaults?: {
        enabled: boolean;
        interval_minutes: number;
        competition_starts_at: string | null;
        competition_ends_at: string | null;
        tick_seconds: number;
        reconcile_seconds: number;
    };
};

export type SiteConfig = {
    allow_registration: boolean;
    phase: string;
    announcement_title: string;
    announcement_body: string;
    announcement_updated_at: string | null;
    updated_at: string;
};

export type AdminRegistrationInvite = InviteStatus & { id: number };

export type AdminMapTemplate = {
    id: number;
    slug: string;
    name: string;
    source_text: string;
    layout: Record<string, unknown>;
    sort_order: number;
    difficulty: number;
    is_active: boolean;
    created_by_user_id: number | null;
    created_at: string;
    updated_at: string;
};

export async function adminGetSystem() {
    return api<SystemHealth>("/api/admin/system");
}

export async function adminListMaps() {
    return api<AdminMapTemplate[]>("/api/admin/maps");
}

export async function adminCreateMap(payload: {
    name: string;
    source_text: string;
    sort_order: number;
    difficulty: number;
    is_active: boolean;
}) {
    return api<AdminMapTemplate>("/api/admin/maps", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminUpdateMap(mapId: number, payload: {
    name: string;
    source_text: string;
    sort_order: number;
    difficulty: number;
    is_active: boolean;
}) {
    return api<AdminMapTemplate>(`/api/admin/maps/${mapId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminDeleteMap(mapId: number) {
    return api<{ deleted_map_id: number }>(`/api/admin/maps/${mapId}`, { method: "DELETE" });
}

export type MapUploadResult = {
    created: AdminMapTemplate[];
    errors: { filename: string; error: string }[];
};

export async function adminUploadMaps(files: File[]) {
    const token = getToken();
    const headers: Record<string, string> = {};
    if (token) headers["Authorization"] = `Bearer ${token}`;
    const form = new FormData();
    for (const file of files) form.append("files", file);
    const res = await fetch("/api/admin/maps/upload", {
        method: "POST", headers, body: form, cache: "no-store",
    });
    const payload = await res.json().catch(() => ({ ok: false })) as ApiResult<MapUploadResult> & { detail?: string };
    if (!res.ok || !payload.ok) throw new Error(payload.detail || `HTTP ${res.status}`);
    return payload.data;
}

export async function adminGetRoundOverview(roundId: number) {
    return api<RoundOverviewUser[]>(`/api/admin/rounds/${roundId}/overview`);
}

export async function adminGetAllSubmissions(roundId: number) {
    return api<AdminAllSubmission[]>(`/api/admin/rounds/${roundId}/all-submissions`);
}

export async function adminRetryMatch(matchId: number) {
    return api<{ match_id: number; task: string }>(`/api/admin/matches/${matchId}/retry`, { method: "POST" });
}

export async function adminResetFailed(roundId: number) {
    return api<{ reset: number }>(`/api/admin/rounds/${roundId}/reset-failed`, { method: "POST" });
}

export async function adminGetAutoRoundConfig() {
    return api<AutoRoundConfig>("/api/admin/auto-round");
}

export async function adminGetSiteConfig() {
    return api<SiteConfig>("/api/admin/site-config");
}

export async function adminListRegistrationInvites() {
    return api<AdminRegistrationInvite[]>("/api/admin/registration-invites");
}

export async function adminCreateRegistrationInvite(payload: {
    max_uses: number;
}) {
    return api<AdminRegistrationInvite>("/api/admin/registration-invites", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminRevokeRegistrationInvite(inviteId: number) {
    return api<AdminRegistrationInvite>(`/api/admin/registration-invites/${inviteId}/revoke`, {
        method: "POST",
    });
}

export async function adminUpdateSiteConfig(payload: {
    allow_registration: boolean;
    phase: string;
    announcement_title: string;
    announcement_body: string;
}) {
    return api<SiteConfig>("/api/admin/site-config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminUpdateAutoRoundConfig(payload: {
    enabled: boolean;
    interval_minutes: number;
    competition_starts_at: string | null;
    competition_ends_at: string | null;
}) {
    return api<AutoRoundConfig>("/api/admin/auto-round", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminTriggerAutoRound() {
    return api<{ task: string; task_id: string }>("/api/admin/auto-round/trigger", {
        method: "POST",
    });
}

// ── baselines ─────────────────────────────────────────────────

export async function adminListBaselines() {
    return api<AdminBaseline[]>("/api/admin/baselines");
}

export async function adminCreateBaseline(payload: {
    display_name: string;
    attack_submission_id: number;
    defense_submission_id: number;
    sort_order: number;
    is_active: boolean;
}) {
    return api<AdminBaseline>("/api/admin/baselines", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminUpdateBaseline(
    baselineId: number,
    payload: { display_name: string; sort_order: number; is_active: boolean },
) {
    return api<AdminBaseline>(`/api/admin/baselines/${baselineId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
}

export async function adminDeleteBaseline(baselineId: number) {
    return api<{ deleted_baseline_id: number }>(`/api/admin/baselines/${baselineId}`, {
        method: "DELETE",
    });
}

export async function adminListAllSubmissions() {
    return api<AdminSubmission[]>("/api/admin/all-submissions");
}

export async function adminImportUsers(text: string, dry_run: boolean) {
    return api<ImportUsersResult>("/api/admin/users/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text, dry_run }),
    });
}

export function connectRoundLive(
    roundId: number,
    onData: (data: RoundLivePayload) => void,
): { close(): void } {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/ws/rounds/${roundId}/live`;
    let ws: WebSocket;
    let destroyed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
        ws = new WebSocket(url);
        ws.onmessage = (event) => {
            try {
                const parsed = JSON.parse(event.data as string) as {
                    type: string;
                    data?: RoundLivePayload;
                };
                if (parsed.type === "round_live" && parsed.data) {
                    onData(parsed.data);
                }
            } catch {
                // ignore malformed push
            }
        };
        ws.onclose = () => {
            if (!destroyed) retryTimer = setTimeout(connect, 3000);
        };
        ws.onerror = () => ws.close();
    }

    connect();
    return {
        close() {
            destroyed = true;
            if (retryTimer) clearTimeout(retryTimer);
            ws.close();
        },
    };
}

export function connectTestRunLive(
    runId: number,
    onData: (data: TestRunLivePayload) => void,
): { close(): void } {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/ws/test/runs/${runId}/live`;
    let ws: WebSocket;
    let destroyed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
        ws = new WebSocket(url);
        ws.onmessage = (event) => {
            try {
                const parsed = JSON.parse(event.data as string) as {
                    type: string;
                    data?: TestRunLivePayload;
                };
                if (parsed.type === "test_run_live" && parsed.data) {
                    onData(parsed.data);
                }
            } catch {
                // ignore malformed push
            }
        };
        ws.onclose = () => {
            if (!destroyed) retryTimer = setTimeout(connect, 3000);
        };
        ws.onerror = () => ws.close();
    }

    connect();
    return {
        close() {
            destroyed = true;
            if (retryTimer) clearTimeout(retryTimer);
            ws.close();
        },
    };
}

export function connectAnnouncementLive(
    onData: (data: SiteConfig) => void,
): { close(): void } {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const url = `${protocol}://${window.location.host}/ws/announcements/live`;
    let ws: WebSocket;
    let destroyed = false;
    let retryTimer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
        ws = new WebSocket(url);
        ws.onmessage = (event) => {
            try {
                const parsed = JSON.parse(event.data as string) as {
                    type: string;
                    data?: SiteConfig;
                };
                if (parsed.type === "announcement_live" && parsed.data) {
                    onData(parsed.data);
                }
            } catch {
                // ignore malformed push
            }
        };
        ws.onclose = () => {
            if (!destroyed) retryTimer = setTimeout(connect, 3000);
        };
        ws.onerror = () => ws.close();
    }

    connect();
    return {
        close() {
            destroyed = true;
            if (retryTimer) clearTimeout(retryTimer);
            ws.close();
        },
    };
}
