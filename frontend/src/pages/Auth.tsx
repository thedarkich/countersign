import { useEffect, useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useSearchParams } from 'react-router-dom'
import { Eye, EyeOff, LockKeyhole } from 'lucide-react'
import { api, getAdminToken } from '../api/client'
import { useLang } from '../i18n'
import { authRequest, useAuth, workspaceDestination } from '../lib/auth'
import { SiteHeader, SiteFooter } from '../components/SiteChrome'

export default function AuthPage({ register = false }: { register?: boolean }) {
  const { tr } = useLang()
  const { user, loading, error: sessionError, signedIn, refresh } = useAuth()
  const [params] = useSearchParams()
  const location = useLocation()
  const next = workspaceDestination(params.get('next'))
  const suffix = params.get('next') ? '?next=' + encodeURIComponent(next) : ''
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [visible, setVisible] = useState(false)
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [message, setMessage] = useState('')
  useEffect(() => {
    setName(''); setEmail(''); setPassword(''); setConfirm(''); setErrors({}); setMessage(''); setVisible(false)
    document.title = (register ? tr('Create account', '创建账户') : tr('Sign in', '登录')) + ' · Countersign'
    window.scrollTo(0, 0)
  }, [register, location.pathname, tr])
  if (user || getAdminToken()) return <Navigate to={next} replace />
  async function submit(event: FormEvent) {
    event.preventDefault()
    if (busy) return
    const invalid: Record<string, string> = {}
    if (register && (name.trim().length < 2 || name.trim().length > 60)) invalid.name = tr('Use 2–60 characters for your name.', '姓名需为 2–60 个字符。')
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim()) || email.trim().length > 254) invalid.email = tr('Enter a valid email address.', '请输入有效的邮箱地址。')
    if (password.length < 10 || password.length > 128) invalid.password = tr('Use 10–128 characters.', '密码需为 10–128 个字符。')
    if (register && password !== confirm) invalid.confirm = tr('Your passwords do not match.', '两次输入的密码不一致。')
    setErrors(invalid); setMessage('')
    if (Object.keys(invalid).length) { document.getElementById(Object.keys(invalid)[0])?.focus(); return }
    setBusy(true)
    try {
      const body: Record<string, string> = register ? { name: name.trim(), email: email.trim(), password } : { email: email.trim(), password }
      const { response, result } = await authRequest(register ? '/api/register' : '/api/login', body)
      if (response.ok && result.user) { setPassword(''); setConfirm(''); signedIn(result.user); return }
      const messages: Record<number, string> = {
        401: tr('Email or password is incorrect.', '邮箱或密码不正确。'),
        403: tr('Refresh this page and try again.', '请刷新页面后重试。'),
        409: tr('This email already has an account. Sign in instead.', '该邮箱已注册，请直接登录。'),
        422: tr('Check your name, email and password.', '请检查姓名、邮箱和密码。'),
        429: tr('Too many attempts. Please retry in 15 minutes.', '尝试过于频繁，请在 15 分钟后重试。'),
        503: tr('Accounts are temporarily unavailable.', '账户服务暂不可用。'),
      }
      setMessage(messages[response.status] ?? tr('Unable to sign in. Please retry.', '暂时无法登录，请重试。'))
    } catch { setMessage(tr('Could not reach the server. Please retry.', '无法连接登录服务，请重试。')) }
    finally { setBusy(false) }
  }
  const fieldError = (key: string) => errors[key] && <p id={key + '-error'} className="auth-field-error">{errors[key]}</p>
  return <div className="public-site"><SiteHeader />
    <main className="auth-main" tabIndex={-1}>
      <div className="auth-intro"><p className="mono-label">// {tr('YOUR RULES. EVERY PAYMENT.', '每笔付款，你来定规则。')}</p><h1>{tr('AI checks the invoice.', 'AI 审票。')}<br /><span>{tr('The contract calls the shots.', '合约拍板。')}</span></h1><p>{tr('AI checks invoices. Your contract enforces your payment rules.', 'AI 检查发票，智能合约按你设定的规则放行或拒付。')}</p>
        <div className="auth-flow"><div className="mono-label">{tr('THE PAYMENT WORKFLOW', '付款流程')}</div>{[
          [tr('Agent requests', 'Agent 提出付款'), tr('Invoice and payment details', '发票与付款信息')],
          [tr('Rules check', '检查付款规则'), tr('Supplier, purchase order and limits', '供应商、采购单与额度')],
          [tr('Pay within policy', '在规则内付款'), tr('People stay in charge of changes', '规则变更仍由人掌控')],
        ].map(([title, text], i) => <div className="auth-flow-row" key={title}><span>{i === 2 ? '✓' : '0' + (i + 1)}</span><div><strong>{title}</strong><p>{text}</p></div></div>)}</div>
        <p className="auth-local-note">{tr('Your invoices are visible only to your account · The ledger and agent history are public', '你的发票仅本账户可见 · 账本与 Agent 历史公开可见')}</p>
      </div>
      <section className="auth-card" aria-labelledby="auth-title"><p className="mono-label">{tr('LET’S GET YOU STARTED', '从这里开始')}</p><h2 id="auth-title">{register ? tr('Your workspace starts here.', '创建你的账户。') : tr('Welcome back.', '欢迎回来。')}</h2><p className="auth-subtitle">{register ? tr('Create an account to get started with Countersign.', '创建账户，开始使用 Countersign。') : tr('Sign in to your Countersign workspace.', '登录你的 Countersign 工作台。')}</p>
        {api.mode === 'mock' && <p className="auth-message">{tr('Mock preview: any details work. Nothing is sent on-chain.', '模拟预览：任意信息均可，不发送链上交易。')}</p>}
        <nav className="auth-tabs" aria-label={tr('Account access mode', '账户访问方式')}><Link to={'/login' + suffix} aria-current={!register ? 'page' : undefined} className={!register ? 'is-active' : ''}>{tr('Sign in', '登录')}</Link><Link to={'/signup' + suffix} aria-current={register ? 'page' : undefined} className={register ? 'is-active' : ''}>{tr('Create account', '创建账户')}</Link></nav>
        <form onSubmit={submit} noValidate aria-busy={busy}>
          <fieldset disabled={busy || loading}>
            {register && <label className="auth-field" htmlFor="name">{tr('Full name', '姓名')}<input id="name" autoComplete="name" maxLength={60} value={name} onChange={e => setName(e.target.value)} placeholder={tr('Your name', '你的姓名')} aria-invalid={!!errors.name} aria-describedby={errors.name ? 'name-error' : undefined} />{fieldError('name')}</label>}
            <label className="auth-field" htmlFor="email">{tr('Email address', '邮箱地址')}<input id="email" type="email" autoComplete="username" maxLength={254} value={email} onChange={e => setEmail(e.target.value)} placeholder="you@company.com" aria-invalid={!!errors.email} aria-describedby={errors.email ? 'email-error' : undefined} />{fieldError('email')}</label>
            <div className="auth-field"><div className="auth-label-row"><label htmlFor="password">{tr('Password', '密码')}</label><span>{tr('10 characters minimum', '至少 10 个字符')}</span></div><div className="auth-password"><input id="password" type={visible ? 'text' : 'password'} autoComplete={register ? 'new-password' : 'current-password'} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} placeholder={tr('Enter your password', '输入密码')} aria-invalid={!!errors.password} aria-describedby={errors.password ? 'password-error' : undefined} /><button type="button" aria-label={visible ? tr('Hide password', '隐藏密码') : tr('Show password', '显示密码')} aria-pressed={visible} onClick={() => setVisible(!visible)}>{visible ? <EyeOff size={18} /> : <Eye size={18} />}</button></div>{fieldError('password')}</div>
            {register && <label className="auth-field" htmlFor="confirm">{tr('Confirm password', '确认密码')}<input id="confirm" type="password" autoComplete="new-password" maxLength={128} value={confirm} onChange={e => setConfirm(e.target.value)} placeholder={tr('Enter your password again', '再次输入密码')} aria-invalid={!!errors.confirm} aria-describedby={errors.confirm ? 'confirm-error' : undefined} />{fieldError('confirm')}</label>}
            {message && <p className="auth-message" role="alert">{message}</p>}
            <button type="submit" className="site-button auth-submit">{busy ? tr('Please wait…', '请稍候…') : register ? tr('Create account', '创建账户') : tr('Sign in', '登录')} <span aria-hidden>→</span></button>
          </fieldset>
        </form>
        {sessionError && <p className="auth-message" role="alert">{sessionError} <button type="button" onClick={() => void refresh()}>{tr('Retry', '重试')}</button></p>}
        <p className="auth-switch">{register ? tr('Already have an account?', '已经有账户？') : tr('New to Countersign?', '第一次使用 Countersign？')} <Link to={(register ? '/login' : '/signup') + suffix}>{register ? tr('Sign in', '登录') : tr('Create an account', '创建账户')}</Link></p>
        <p className="auth-switch">{tr('Have a team access token?', '有团队访问令牌？')} <Link to={'/team-token' + (next !== '/inbox' ? '?next=' + encodeURIComponent(next) : '')}>{tr('Use it instead', '改用令牌')}</Link></p>
        <div className="auth-access-note"><LockKeyhole size={18} /><p>{tr('This is your workspace login.', '这是工作台登录。')}<br />{tr('Owner actions still need the owner wallet.', '所有者操作仍需所有者钱包签名。')}</p></div>
      </section>
    </main><SiteFooter />
  </div>
}
