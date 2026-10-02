import { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";

/**
 * The backend's identity_from_claims requires a real org_id claim (the
 * same org-per-tenant pattern Chapter 35 already proves); Auth0 only
 * includes that claim when an organization is explicitly requested at
 * login, so this asks for one rather than logging in to the tenant's
 * default, org-less context.
 *
 * This asks for the real org_id (e.g. "org_CZKzkSVB0Hbngqd9"), not a
 * friendly org name: this tenant's /authorize rejects a plain name
 * ("authorization request parameter organization must be an
 * organization id") unless "Use Organization Names in Authentication
 * API" is turned on, which is a tenant-level flag, not something this
 * SPA can enable for itself. A real product would resolve a typed
 * company name to its org_id via a backend lookup (home realm
 * discovery); asking for the id directly is the honest placeholder
 * for that until that lookup exists.
 */
export default function StudioLoginGate({ children }: { children: React.ReactNode }) {
  const { isLoading, isAuthenticated, error, user, loginWithRedirect, logout } = useAuth0();
  const [organization, setOrganization] = useState("");

  if (isLoading) {
    return <p className="studio-auth-status">Checking your session…</p>;
  }

  if (error) {
    return <p className="studio-auth-status studio-auth-error">{error.message}</p>;
  }

  if (!isAuthenticated) {
    return (
      <section className="studio-auth-gate">
        <p className="eyebrow">RESEARCHER SIGN-IN</p>
        <h2>Sign in to your lab's organization</h2>
        <p className="lede">
          Your own uploads and search results are isolated to your organization; no other lab
          can see them, and you cannot see theirs.
        </p>
        <div className="studio-auth-controls">
          <label htmlFor="studio-org">Organization id</label>
          <input
            id="studio-org"
            value={organization}
            onChange={(event) => setOrganization(event.target.value)}
            placeholder="org_..."
          />
          <button
            type="button"
            disabled={organization.trim().length === 0}
            onClick={() =>
              loginWithRedirect({
                authorizationParams: { organization: organization.trim() },
              })
            }
          >
            Sign in
          </button>
        </div>
      </section>
    );
  }

  return (
    <div>
      <div className="studio-auth-banner">
        <span>Signed in as {user?.email ?? user?.name ?? "researcher"}</span>
        <button
          type="button"
          className="quiet"
          onClick={() => logout({ logoutParams: { returnTo: window.location.origin } })}
        >
          Sign out
        </button>
      </div>
      {children}
    </div>
  );
}
