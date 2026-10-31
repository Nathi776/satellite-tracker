import { ALERT_LEADS, usePushAlerts } from "../hooks/usePushAlerts";

const NOTE: Record<string, string> = {
  unsupported: "This browser can't receive alerts. On an iPhone, add the app to your Home Screen first.",
  insecure: "Alerts need a secure (https) page.",
  unavailable: "Alerts aren't switched on for this server.",
  blocked: "Notifications are blocked for this site. Allow them in your browser's site settings.",
};

/** "Alert me before a pass": push notifications that arrive even when the app is closed. */
export default function PushAlerts({ location }: { location: { lat: number; lon: number } | null }) {
  const { status, prefs, setPref, enable, disable, sendTest, busy, error } = usePushAlerts(location);

  if (status === "checking") return null;
  const on = status === "on";
  const usable = on || status === "off";

  return (
    <div className="alerts">
      <label className="layers__row" title={location ? undefined : "Use My Location first"}>
        <input
          type="checkbox"
          checked={on}
          disabled={!usable || busy || (!on && !location)}
          onChange={() => (on ? disable() : enable())}
        />
        <span className="layers__label">Alert me before passes</span>
      </label>

      {!usable && <p className="alerts__note">{NOTE[status]}</p>}
      {status === "off" && !location && <p className="alerts__note">Set your location first.</p>}

      {on && (
        <div className="alerts__opts">
          <label>
            Tell me{" "}
            <select value={prefs.lead} onChange={e => setPref({ lead: Number(e.target.value) })}>
              {ALERT_LEADS.map(m => (
                <option key={m} value={m}>
                  {m} min before
                </option>
              ))}
            </select>
          </label>
          <label className="layers__row">
            <input
              type="checkbox"
              checked={prefs.visibleOnly}
              onChange={e => setPref({ visibleOnly: e.target.checked })}
            />
            <span className="layers__label">Only passes I can see</span>
          </label>
          <button type="button" className="layers__link" onClick={sendTest}>
            Send a test alert
          </button>
        </div>
      )}
      {error && (
        <p className="alerts__note alerts__note--error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
