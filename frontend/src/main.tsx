import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Auth0Provider } from "@auth0/auth0-react";

import App from "./App";
import { AUTH0_AUDIENCE, AUTH0_CLIENT_ID, AUTH0_DOMAIN, AUTH0_SCOPE } from "./auth0Config";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <Auth0Provider
      domain={AUTH0_DOMAIN}
      clientId={AUTH0_CLIENT_ID}
      authorizationParams={{
        redirect_uri: window.location.origin,
        audience: AUTH0_AUDIENCE,
        scope: AUTH0_SCOPE,
      }}
      useRefreshTokens
      useRefreshTokensFallback
    >
      <App />
    </Auth0Provider>
  </StrictMode>,
);
