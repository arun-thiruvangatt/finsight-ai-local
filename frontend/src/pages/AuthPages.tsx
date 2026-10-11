import { FormEvent, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "../auth";
import { Err } from "../components/ui";

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try { await login(email, password); nav("/dashboard"); } catch (err: any) { setError(err.message); }
  };
  return (
    <div className="center">
      <form className="card auth" onSubmit={submit}>
        <h2>FinSight <span className="accent">AI</span></h2>
        <p className="muted">Sign in to your finance workspace</p>
        <input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
        <Err msg={error} />
        <button>Sign in</button>
        <small>No account? <Link to="/register">Register</Link></small>
      </form>
    </div>
  );
}

export function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [f, setF] = useState({ full_name: "", email: "", password: "" });
  const [error, setError] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try { await register(f.email, f.password, f.full_name); nav("/dashboard"); } catch (err: any) { setError(err.message); }
  };
  return (
    <div className="center">
      <form className="card auth" onSubmit={submit}>
        <h2>Create account</h2>
        <input placeholder="Full name" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} required />
        <input type="email" placeholder="Email" value={f.email} onChange={(e) => setF({ ...f, email: e.target.value })} required />
        <input type="password" placeholder="Password (min 8 chars)" minLength={8} value={f.password}
          onChange={(e) => setF({ ...f, password: e.target.value })} required />
        <Err msg={error} />
        <button>Register</button>
        <small>Have an account? <Link to="/login">Sign in</Link></small>
      </form>
    </div>
  );
}
