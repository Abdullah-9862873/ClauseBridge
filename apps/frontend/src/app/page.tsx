import Link from 'next/link';

export default function Home() {
  return (
    <div className="login-page">
      <div className="login-brand">
        <div>
          <div className="mark">
            <svg width="24" height="24" viewBox="0 0 26 26" fill="none">
              <path d="M4 21V6.5C4 5.12 5.12 4 6.5 4H15L22 11V19.5C22 20.88 20.88 22 19.5 22H6.5C5.12 22 4 20.88 4 19.5Z" stroke="#F7F6F1" strokeWidth="1.4"/>
              <path d="M15 4V9.5C15 10.33 15.67 11 16.5 11H22" stroke="#F7F6F1" strokeWidth="1.4"/>
              <line x1="8" y1="14.5" x2="17.5" y2="14.5" stroke="#B23B2E" strokeWidth="1.4"/>
              <line x1="8" y1="17.6" x2="14" y2="17.6" stroke="#F7F6F1" strokeWidth="1.4"/>
            </svg>
            Clausebridge
          </div>
        </div>
        <blockquote>
          &ldquo;It didn&rsquo;t catch a typo. It caught that our counterparty had quietly widened a liability cap &mdash; three clauses away from where anyone was looking.&rdquo;
          <div className="attr">Meredith Okonkwo &mdash; Partner, Voss &amp; Okonkwo LLP</div>
        </blockquote>
        <div style={{ fontSize: '12.5px', color: 'var(--sidebar-text)' }}>&copy; 2026 Clausebridge</div>
      </div>

      <div className="login-form-side">
        <div className="login-card">
          <h1>ClauseBridge</h1>
          <p className="lede">AI-assisted legal document diligence. Classify, extract, and flag clauses with confidence.</p>
          <Link href="/login" className="btn btn-primary" style={{ width: '100%', marginTop: '6px' }}>
            Get started
          </Link>
          <p className="login-foot" style={{ marginTop: '20px' }}>
            Secure document diligence for legal teams
          </p>
        </div>
      </div>
    </div>
  );
}
