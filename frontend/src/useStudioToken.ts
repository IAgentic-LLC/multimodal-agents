import { useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";

import { AUTH0_AUDIENCE, AUTH0_SCOPE } from "./auth0Config";

/** A fresh, real access token for the studio API, silently refreshed by
 * the SDK when the cached one is close to expiry. Never logs or exposes
 * the token itself beyond returning it to the caller that needs it for
 * one request.
 */
export function useStudioToken() {
  const { getAccessTokenSilently } = useAuth0();

  return useCallback(async () => {
    return getAccessTokenSilently({
      authorizationParams: { audience: AUTH0_AUDIENCE, scope: AUTH0_SCOPE },
    });
  }, [getAccessTokenSilently]);
}
