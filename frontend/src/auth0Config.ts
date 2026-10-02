// Auth0 domain, client ID, and audience are public identifiers, not
// secrets: the SPA client is a public OAuth client by design (PKCE, no
// client secret), safe to bake into the built bundle.
export const AUTH0_DOMAIN = "dev-a73uyb0st1rx7y8q.eu.auth0.com";
export const AUTH0_CLIENT_ID = "IFcia2sAmBHs5sodQpgaw1fpOqd75q9m";
export const AUTH0_AUDIENCE = "https://multimodal-agent-studio.dev/api";
export const AUTH0_SCOPE = "write:studio_evidence";
