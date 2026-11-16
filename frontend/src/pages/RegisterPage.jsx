/** Sign up. Timezone is detected automatically, because streak days follow the user's local midnight. */
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Banner } from '../components/ui/Banner';
import { Button } from '../components/ui/Button';
import { PasswordField, TextField } from '../components/ui/Field';
import { useDocumentTitle } from '../components/ui/PageHeader';
import { AuthShell } from './AuthShell';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function detectTimezone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC';
  } catch {
    return 'UTC';
  }
}

export default function RegisterPage() {
  const { register } = useAuth();
  const location = useLocation();
  const [values, setValues] = useState({ display_name: '', email: '', password: '' });
  const [touched, setTouched] = useState({});
  const [serverError, setServerError] = useState(null);
  const [emailTaken, setEmailTaken] = useState(false);
  const [busy, setBusy] = useState(false);
  const timezone = detectTimezone();
  useDocumentTitle('Create your account');

  const name = values.display_name.trim();
  const errors = {
    display_name: name.length < 2 ? 'Tell us what to call you (at least 2 characters).' : name.length > 40 ? 'Please keep it to 40 characters or fewer.' : null,
    email: !EMAIL_PATTERN.test(values.email.trim()) ? 'Enter your email address, like name@example.com.' : emailTaken ? 'That email already has an account.' : null,
    password: values.password.length < 8 ? 'Use at least 8 characters.' : values.password.length > 128 ? 'Please keep it to 128 characters or fewer.' : null,
  };

  const field = (key) => ({
    value: values[key],
    onChange: (event) => {
      if (key === 'email') setEmailTaken(false);
      setValues((prev) => ({ ...prev, [key]: event.target.value }));
    },
    onBlur: () => setTouched((prev) => ({ ...prev, [key]: true })),
    error: touched[key] ? errors[key] : null,
  });

  const submit = async (event) => {
    event.preventDefault();
    setTouched({ display_name: true, email: true, password: true });
    if (errors.display_name || errors.email || errors.password) return;
    setBusy(true);
    setServerError(null);
    try {
      await register({ email: values.email.trim(), password: values.password, display_name: name, timezone });
    } catch (error) {
      if (error.code === 'email_taken') setEmailTaken(true);
      else setServerError(error.message);
      setBusy(false);
    }
  };

  return (
    <AuthShell
      heading="Take your first step on stage"
      subheading="Free to start. Your first session takes about a minute."
      footer={
        <>
          Already have an account?{' '}
          <Link to="/login" state={location.state} className="font-semibold text-ink underline underline-offset-2 hover:text-amber-bright">
            Log in
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        {serverError && <Banner tone="danger">{serverError}</Banner>}
        <TextField label="What should we call you?" autoComplete="name" {...field('display_name')} />
        <TextField label="Email" type="email" autoComplete="email" inputMode="email" {...field('email')} />
        <PasswordField autoComplete="new-password" hint="At least 8 characters." {...field('password')} />
        <p className="text-xs text-ink-muted">We'll count your streak days in {timezone}. You can change this later in Settings.</p>
        <Button type="submit" size="lg" loading={busy} className="w-full">
          Create my account
        </Button>
      </form>
    </AuthShell>
  );
}
