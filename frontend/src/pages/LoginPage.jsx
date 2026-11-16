/** Log in. Field errors show after the user leaves a field, so they aren't scolded while typing. */
import { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Banner } from '../components/ui/Banner';
import { Button } from '../components/ui/Button';
import { PasswordField, TextField } from '../components/ui/Field';
import { useDocumentTitle } from '../components/ui/PageHeader';
import { AuthShell } from './AuthShell';

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const { login } = useAuth();
  const location = useLocation();
  const [values, setValues] = useState({ email: '', password: '' });
  const [touched, setTouched] = useState({});
  const [serverError, setServerError] = useState(null);
  const [busy, setBusy] = useState(false);
  useDocumentTitle('Log in');

  const errors = {
    email: !EMAIL_PATTERN.test(values.email.trim()) ? 'Enter your email address, like name@example.com.' : null,
    password: !values.password ? 'Enter your password.' : null,
  };

  const field = (name) => ({
    value: values[name],
    onChange: (event) => setValues((prev) => ({ ...prev, [name]: event.target.value })),
    onBlur: () => setTouched((prev) => ({ ...prev, [name]: true })),
    error: touched[name] ? errors[name] : null,
  });

  const submit = async (event) => {
    event.preventDefault();
    setTouched({ email: true, password: true });
    if (errors.email || errors.password) return;
    setBusy(true);
    setServerError(null);
    try {
      await login({ email: values.email.trim(), password: values.password });
      // RedirectIfAuthed handles the way back to wherever the user was heading.
    } catch (error) {
      setServerError(error.code === 'invalid_credentials' ? "That email and password don't match. Check them and try again." : error.message);
      setBusy(false);
    }
  };

  return (
    <AuthShell
      heading="Welcome back"
      subheading="The stage is just as you left it."
      footer={
        <>
          New here?{' '}
          <Link to="/register" state={location.state} className="font-semibold text-ink underline underline-offset-2 hover:text-amber-bright">
            Create your account
          </Link>
        </>
      }
    >
      <form onSubmit={submit} noValidate className="flex flex-col gap-4">
        {serverError && <Banner tone="danger">{serverError}</Banner>}
        <TextField label="Email" type="email" autoComplete="email" inputMode="email" {...field('email')} />
        <PasswordField autoComplete="current-password" {...field('password')} />
        <Button type="submit" size="lg" loading={busy} className="mt-2 w-full">
          Log in
        </Button>
      </form>
    </AuthShell>
  );
}
