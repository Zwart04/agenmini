// Agen Mini connection-only fork. Provider implementations retain upstream semantics.
package handlers

import (
	"9router/proxy/internal/db"
	"9router/proxy/internal/handlers/chat"
	"9router/proxy/internal/handlers/dashboard"
	"9router/proxy/internal/handlers/oauth"
	"9router/proxy/internal/handlers/shared"
	"9router/proxy/internal/middleware"
	"github.com/go-chi/chi/v5"
	"net/http"
)

type TokenSaverConfig = shared.TokenSaverConfig

func NewTokenSaverConfig(rtk, caveman, ponytail bool) *TokenSaverConfig {
	return shared.NewTokenSaverConfig(rtk, caveman, ponytail)
}
func SetupServerRouter(r *chi.Mux, repo *db.Repo, ts *TokenSaverConfig) {
	c := chat.NewChatHandler(repo, ts)
	d := dashboard.NewDashboardHandler(repo)
	o := oauth.NewOAuthHandler(repo)
	r.Get("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"status":"ok","engine":"agenmini-gateway"}`))
	})
	r.Get("/api/version", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		w.Write([]byte(`{"currentVersion":"0.9.0","engine":"agenmini-gateway","goVersion":"native","connectionOnly":true}`))
	})
	r.Get("/callback", o.HandleCallbackPage)
	r.Post("/api/auth/login", d.HandleAuthLogin)
	r.Group(func(r chi.Router) {
		r.Use(middleware.RequireApiKey(repo))
		r.Post("/chat/completions", c.HandleChatCompletions)
		r.Post("/messages", c.HandleMessages)
		r.Post("/messages/count_tokens", c.HandleCountTokens)
		r.Post("/responses", c.HandleResponses)
		r.Get("/models", c.HandleModels)
	})
	r.Group(func(r chi.Router) {
		r.Use(middleware.RequireAdminAuth())
		r.Get("/api/models", c.HandleModels)
		r.Get("/api/providers", d.HandleGetProvidersClient)
		r.Get("/api/connections", d.HandleGetConnections)
		r.Post("/api/connections", d.HandleCreateConnection)
		r.Post("/api/providers", d.HandleCreateConnection)
		r.Delete("/api/providers/{id}", d.HandleDeleteConnection)
		r.Put("/api/providers/{id}", d.HandleUpdateConnection)
		r.Post("/api/providers/{id}/test", d.HandleTestConnection)
		r.Get("/api/providers/{id}/models", d.HandleGetConnectionModels)
		r.Get("/api/provider-nodes", d.HandleGetProviderNodes)
		r.Post("/api/provider-nodes", d.HandleCreateProviderNode)
		r.Get("/api/keys", d.HandleGetApiKeys)
		r.Post("/api/keys", d.HandleCreateApiKey)
		r.Get("/api/combos", d.HandleGetCombos)
		r.Post("/api/combos", d.HandleCreateCombo)
		r.Get("/api/models/disabled", d.HandleGetDisabledModels)
		r.Get("/api/models/custom", d.HandleGetCustomModels)
		r.Post("/api/models/custom", d.HandleSaveCustomModel)
		r.Get("/api/settings", d.HandleGetSettings)
		r.Patch("/api/settings", d.HandleUpdateSettings)
		mountOAuthRoutes(r, o)
	})
}

func mountOAuthRoutes(r interface {
	Get(pattern string, handlerFn http.HandlerFunc)
	Post(pattern string, handlerFn http.HandlerFunc)
}, oauthH *oauth.OAuthHandler) {
	r.Post("/api/oauth/{provider}/import", oauthH.HandleOAuthImport)
	r.Get("/api/oauth/kiro/social-authorize", oauthH.HandleOAuthKiroSocialAuthorize)
	r.Post("/api/oauth/kiro/social-exchange", oauthH.HandleOAuthKiroSocialExchange)
	r.Post("/api/oauth/kiro/import", oauthH.HandleKiroImport)
	r.Post("/api/oauth/kiro/import-cli-proxy", oauthH.HandleKiroImportCliProxy)
	r.Get("/api/oauth/kiro/auto-import", oauthH.HandleKiroAutoImport)
	r.Post("/api/oauth/kiro/api-key", oauthH.HandleKiroAPIKey)
	r.Post("/api/oauth/codex/bulk-import", oauthH.HandleOAuthCodexBulkImport)
	r.Post("/api/oauth/grok-cli/bulk-import", oauthH.HandleOAuthGrokCliBulkImport)
	r.Post("/api/oauth/freebuff/initiate", oauthH.HandleFreebuffInitiate)
	r.Post("/api/oauth/freebuff/poll", oauthH.HandleFreebuffPoll)
	r.Get("/api/oauth/freebuff/session", oauthH.HandleFreebuffSessionStatus)
	r.Post("/api/oauth/freebuff/session/switch", oauthH.HandleFreebuffSessionSwitch)
	r.Get("/api/oauth/antigravity/authorize", oauthH.HandleAntigravityAuthorize)
	r.Post("/api/oauth/antigravity/exchange", oauthH.HandleAntigravityExchange)
	r.Get("/api/oauth/cline/authorize", oauthH.HandleClineAuthorize)
	r.Post("/api/oauth/cline/exchange", oauthH.HandleClineExchange)
	r.Get("/api/oauth/pkce/authorize", oauthH.HandlePKCEAuthorize)
	r.Post("/api/oauth/pkce/exchange", oauthH.HandlePKCEExchange)
	// Codex's OAuth client only accepts its registered loopback redirect URI,
	// so the callback is served by a dedicated fixed-port listener rather than
	// the dashboard's /callback page. See internal/handlers/oauth/codex_proxy.go.
	r.Get("/api/oauth/codex/start-proxy", oauthH.HandleCodexStartProxy)
	r.Get("/api/oauth/codex/poll-status", oauthH.HandleCodexPollStatus)
	r.Get("/api/oauth/codex/stop-proxy", oauthH.HandleCodexStopProxy)
	r.Get("/api/oauth/authcode/authorize", oauthH.HandleAuthCodeAuthorize)
	r.Post("/api/oauth/authcode/exchange", oauthH.HandleAuthCodeExchange)
	r.Get("/api/oauth/trae/authorize", oauthH.HandleTraeAuthorize)
	r.Post("/api/oauth/trae/exchange", oauthH.HandleTraeExchange)
	r.Get("/api/oauth/windsurf/authorize", oauthH.HandleWindsurfAuthorize)
	r.Post("/api/oauth/windsurf/exchange", oauthH.HandleWindsurfExchange)
	r.Get("/api/oauth/zed/authorize", oauthH.HandleZedAuthorize)
	r.Post("/api/oauth/zed/exchange", oauthH.HandleZedExchange)
	r.Post("/api/oauth/device/start", oauthH.HandleDeviceStart)
	r.Post("/api/oauth/device/poll", oauthH.HandleDevicePoll)
	r.Post("/api/oauth/cursor/import", oauthH.HandleCursorImport)
	r.Get("/api/oauth/cursor/auto-import", oauthH.HandleCursorAutoImport)
	r.Get("/api/oauth/kimchi/authorize", oauthH.HandleKimchiAuthorize)
	r.Post("/api/oauth/kimchi/exchange", oauthH.HandleKimchiExchange)
	r.Post("/api/oauth/gitlab/pat", oauthH.HandleGitlabPAT)
	r.Post("/api/oauth/iflow/cookie", oauthH.HandleIflowCookie)
	r.Get("/api/oauth/xiaomi-mimo/authorize", oauthH.HandleMimoAuthorize)
	r.Post("/api/oauth/xiaomi-mimo/exchange", oauthH.HandleMimoExchange)
}

// SetupServerRouter mounts public endpoints (/health, /api/hello) and
// API-key protected routes (all engine + admin routes) on the chi router.
