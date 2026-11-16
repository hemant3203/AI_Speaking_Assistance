/** Profile, sign out, the coming-soon API key card, and account deletion behind a password check. */
import { useMemo, useState } from 'react';
import { KeyRound, LogOut, TriangleAlert } from 'lucide-react';
import { deleteMe, updateMe } from '../api/auth';
import { useAuth } from '../context/AuthContext';
import { useToast } from '../context/ToastContext';
import { Button } from '../components/ui/Button';
import { Dialog } from '../components/ui/Dialog';
import { PasswordField, SelectField, TextField } from '../components/ui/Field';
import { PageHeader } from '../components/ui/PageHeader';

function timezoneOptions(current) {
  let zones = [];
  try {
    zones = Intl.supportedValuesOf('timeZone');
  } catch {
    zones = ['UTC'];
  }
  // A stored zone may not be in this browser's list, and a select can't show what it doesn't list.
  return current && !zones.includes(current) ? [current, ...zones] : zones;
}

function ProfileCard() {
  const { user, setUser } = useAuth();
  const toast = useToast();
  const [name, setName] = useState(user.display_name);
  const [timezone, setTimezone] = useState(user.timezone);
  const [busy, setBusy] = useState(false);
  const [touched, setTouched] = useState(false);
  const zones = useMemo(() => timezoneOptions(user.timezone), [user.timezone]);

  const trimmed = name.trim();
  const error = trimmed.length < 2 ? 'Use at least 2 characters.' : trimmed.length > 40 ? 'Please keep it to 40 characters or fewer.' : null;
  const dirty = trimmed !== user.display_name || timezone !== user.timezone;

  const save = async (event) => {
    event.preventDefault();
    setTouched(true);
    if (error || !dirty) return;
    setBusy(true);
    try {
      const { user: next } = await updateMe({ display_name: trimmed, timezone });
      setUser(next);
      toast.success('Saved. Your profile is up to date.');
    } catch (err) {
      toast.error(err.message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="profile-heading" className="card p-5 sm:p-6">
      <h2 id="profile-heading" className="text-xl font-bold">
        Profile
      </h2>
      <form onSubmit={save} noValidate className="mt-4 flex max-w-md flex-col gap-4">
        <TextField label="Email" value={user.email} disabled readOnly hint="Your email can't be changed yet." />
        <TextField label="Display name" value={name} onChange={(event) => setName(event.target.value)} onBlur={() => setTouched(true)} error={touched ? error : null} autoComplete="name" />
        <SelectField label="Timezone" value={timezone} onChange={(event) => setTimezone(event.target.value)} hint="Your streak day ends at midnight here.">
          {zones.map((zone) => (
            <option key={zone} value={zone}>
              {zone.replaceAll('_', ' ')}
            </option>
          ))}
        </SelectField>
        <div>
          <Button type="submit" loading={busy} disabled={!dirty}>
            Save changes
          </Button>
        </div>
      </form>
    </section>
  );
}

function DangerZone() {
  const { setUser } = useAuth();
  const toast = useToast();
  const [open, setOpen] = useState(false);
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  const close = () => {
    setOpen(false);
    setPassword('');
    setError(null);
  };

  const confirm = async (event) => {
    event.preventDefault();
    if (!password) {
      setError('Enter your password to confirm.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await deleteMe(password);
      toast.info('Your account and all your data have been deleted.');
      setUser(null);
    } catch (err) {
      setError(err.status === 401 || err.status === 403 || err.code === 'invalid_credentials' ? "That password doesn't match." : err.message);
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="danger-heading" className="card border-danger/50 p-5 sm:p-6">
      <h2 id="danger-heading" className="flex items-center gap-2 text-xl font-bold">
        <TriangleAlert aria-hidden="true" className="size-5 text-danger" />
        Danger zone
      </h2>
      <p className="mt-2 max-w-xl text-sm text-ink-soft">
        Deleting your account removes your sessions, transcripts, streak, XP and badges for good. We can't undo this.
      </p>
      <Button variant="danger" onClick={() => setOpen(true)} className="mt-4">
        Delete my account
      </Button>

      <Dialog open={open} onClose={close} title="Delete your account?">
        <form onSubmit={confirm} noValidate>
          <p className="text-sm text-ink-soft">All your sessions and progress will be permanently deleted. Enter your password to confirm.</p>
          <div className="mt-4">
            <PasswordField label="Your password" value={password} onChange={(event) => setPassword(event.target.value)} error={error} autoComplete="current-password" />
          </div>
          <div className="mt-5 flex flex-wrap justify-end gap-2">
            <Button variant="secondary" onClick={close}>
              Keep my account
            </Button>
            <Button type="submit" variant="danger" loading={busy}>
              Delete everything
            </Button>
          </div>
        </form>
      </Dialog>
    </section>
  );
}

export default function SettingsPage() {
  const { logout } = useAuth();
  return (
    <div className="flex max-w-3xl flex-col gap-5">
      <PageHeader title="Settings" />
      <ProfileCard />

      <section aria-labelledby="byok-heading" className="card p-5 opacity-90 sm:p-6">
        <div className="flex flex-wrap items-center gap-2.5">
          <KeyRound aria-hidden="true" className="size-5 text-ink-muted" />
          <h2 id="byok-heading" className="text-xl font-bold">
            Bring your own Gemini API key
          </h2>
          <span className="rounded-full border border-line-strong px-2.5 py-0.5 text-xs font-semibold text-ink-soft">Coming soon</span>
        </div>
        <p className="mt-2 max-w-xl text-sm text-ink-soft">Use your own key to practise beyond the daily limit. We're still building this one.</p>
        <div className="mt-4 max-w-md">
          <TextField label="API key" disabled placeholder="Not available yet" />
        </div>
      </section>

      <section aria-labelledby="session-heading" className="card flex flex-wrap items-center justify-between gap-4 p-5 sm:p-6">
        <div>
          <h2 id="session-heading" className="text-xl font-bold">
            Log out
          </h2>
          <p className="mt-1 text-sm text-ink-soft">You'll need your email and password to come back.</p>
        </div>
        <Button variant="secondary" icon={LogOut} onClick={logout}>
          Log out
        </Button>
      </section>

      <DangerZone />
    </div>
  );
}
