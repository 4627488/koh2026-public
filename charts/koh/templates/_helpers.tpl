{{- define "koh.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "koh.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := include "koh.name" . -}}
{{- if eq .Release.Name $name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "koh.labels" -}}
app.kubernetes.io/name: {{ include "koh.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "koh.selectorLabels" -}}
app.kubernetes.io/name: {{ include "koh.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "koh.sharedVolumeClaimName" -}}
{{- if .Values.storage.existingClaim -}}
{{- .Values.storage.existingClaim -}}
{{- else -}}
{{- printf "%s-data" (include "koh.fullname" .) -}}
{{- end -}}
{{- end -}}

{{- define "koh.migrationEnv" -}}
- name: KOH_DATA_DIR
  value: {{ .Values.env.dataDir | quote }}
- name: STRATEGY_WINDOW_MINUTES
  value: {{ .Values.env.strategyWindowMinutes | quote }}
- name: AUTO_ROUND_ENABLED
  value: {{ .Values.env.autoRoundEnabled | quote }}
- name: AUTO_ROUND_INTERVAL_MINUTES
  value: {{ .Values.env.autoRoundIntervalMinutes | quote }}
- name: AUTO_ROUND_STRATEGY_WINDOW_MINUTES
  value: {{ .Values.env.autoRoundStrategyWindowMinutes | quote }}
- name: AUTO_ROUND_MAX_OPEN_ROUNDS
  value: {{ .Values.env.autoRoundMaxOpenRounds | quote }}
- name: AUTO_ROUND_MAX_PENDING_MATCHES
  value: {{ .Values.env.autoRoundMaxPendingMatches | quote }}
- name: AUTO_ROUND_TICK_SECONDS
  value: {{ .Values.env.autoRoundTickSeconds | quote }}
- name: AUTO_ROUND_RECONCILE_SECONDS
  value: {{ .Values.env.autoRoundReconcileSeconds | quote }}
- name: CORS_ORIGINS
  value: {{ toJson .Values.env.corsOrigins | quote }}
- name: KOH_ADMIN_USERNAME
  value: {{ .Values.env.adminUsername | quote }}
- name: KOH_ADMIN_PASSWORD
  value: {{ .Values.env.adminPassword | quote }}
- name: SECRET_KEY
  value: {{ .Values.env.secretKey | quote }}
- name: DATABASE_URL
  value: {{ .Values.env.databaseUrl | quote }}
- name: REDIS_URL
  value: {{ .Values.env.redisUrl | quote }}
{{- end -}}
