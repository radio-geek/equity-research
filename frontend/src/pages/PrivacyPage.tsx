export default function PrivacyPage() {
  return (
    <div className="legal-page">
      <h1>Privacy Policy</h1>
      <p className="legal-meta">Effective date: April 2025 &nbsp;·&nbsp; Last updated: April 2025</p>

      <h2>1. Overview</h2>
      <p>
        valyu ("we", "us", "our") is committed to protecting your privacy. This Privacy Policy explains
        what information we collect, how we use it, and your rights with respect to your data. By using
        the Service, you agree to the collection and use of information in accordance with this policy.
      </p>

      <h2>2. Information We Collect</h2>
      <p>We collect the following categories of information:</p>

      <p><strong>Google Account Information (when you sign in)</strong></p>
      <ul>
        <li>Name</li>
        <li>Email address</li>
        <li>Profile picture URL</li>
      </ul>
      <p>This information is provided by Google via OAuth and stored in our database to identify your account.</p>

      <p><strong>Usage Data</strong></p>
      <ul>
        <li>Stock symbols you search and reports you generate (symbol + timestamp)</li>
        <li>PDF downloads (symbol + timestamp)</li>
        <li>Section feedback and star ratings you submit</li>
        <li>Contact support messages (name, email, message)</li>
      </ul>

      <p><strong>Session Data</strong></p>
      <ul>
        <li>A JWT (JSON Web Token) is stored in your browser's <code>localStorage</code> to keep you signed in. This is not a cookie.</li>
        <li>Session metadata (IP address, user-agent) is stored server-side for security and rate-limiting purposes.</li>
      </ul>

      <h2>3. How We Use Your Information</h2>
      <ul>
        <li><strong>Authentication:</strong> to identify you and maintain your session.</li>
        <li><strong>Service delivery:</strong> to generate and associate research reports with your account.</li>
        <li><strong>Quality improvement:</strong> to analyse feedback and improve report accuracy.</li>
        <li><strong>Support:</strong> to respond to contact messages you submit.</li>
        <li><strong>Abuse prevention:</strong> to enforce rate limits using your user ID or IP address.</li>
      </ul>
      <p>We do not sell, rent, or share your personal information with advertisers.</p>

      <h2>4. Third Parties We Share Data With</h2>
      <ul>
        <li>
          <strong>Google</strong> — provides OAuth sign-in. Your use of Google sign-in is governed by{' '}
          <a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer">
            Google's Privacy Policy
          </a>. We receive only your basic profile (name, email, picture).
        </li>
        <li>
          <strong>OpenAI</strong> — AI models power report generation. We send only the company stock
          symbol and publicly available financial data to OpenAI. No personal user information is
          transmitted.
        </li>
        <li>
          <strong>Neon</strong> — our PostgreSQL database is hosted on Neon (neon.tech). User profiles,
          usage logs, and contact messages are stored here. Data is hosted in the cloud and subject to
          Neon's data processing terms.
        </li>
        <li>
          <strong>Vercel</strong> — our frontend is hosted on Vercel, which may log request IP addresses
          and user-agent strings for operational purposes.
        </li>
        <li>
          <strong>Yahoo Finance (yfinance)</strong> — used to fetch live market index data (Nifty 50,
          Sensex, Nifty Bank). No personal user data is sent to Yahoo Finance.
        </li>
      </ul>

      <h2>5. Data Retention</h2>
      <ul>
        <li>Account data (name, email, picture) is retained while your account is active.</li>
        <li>Contact support messages are retained for up to 2 years.</li>
        <li>Usage logs (report generation, PDF downloads) are retained indefinitely in anonymised or aggregated form for analytics.</li>
        <li>Session tokens are invalidated when you sign out.</li>
      </ul>

      <h2>6. Security</h2>
      <p>
        All data is transmitted over HTTPS. We use JWT tokens for session management and do not store
        passwords. Our database enforces access controls and is not publicly accessible. However, no
        method of transmission over the Internet is 100% secure, and we cannot guarantee absolute security.
      </p>

      <h2>7. Your Rights</h2>
      <p>You have the right to:</p>
      <ul>
        <li>Request a copy of the personal data we hold about you.</li>
        <li>Request correction of inaccurate data.</li>
        <li>Request deletion of your account and associated personal data.</li>
      </ul>
      <p>
        To exercise any of these rights, email us at{' '}
        <a href="mailto:investment.research50@gmail.com">investment.research50@gmail.com</a>. We will
        respond within 30 days.
      </p>

      <h2>8. Cookies &amp; Local Storage</h2>
      <p>
        valyu does not use advertising cookies or third-party tracking cookies. We store your
        authentication token in <code>localStorage</code> (not a cookie). We may set a short-lived
        session cookie during Google OAuth sign-in (used only to prevent CSRF attacks during the login
        flow, then deleted immediately after).
      </p>

      <h2>9. Children's Privacy</h2>
      <p>
        The Service is not directed at persons under 18 years of age. We do not knowingly collect
        personal data from children. If you believe a child has provided us with personal information,
        please contact us and we will delete it promptly.
      </p>

      <h2>10. Changes to This Policy</h2>
      <p>
        We may update this Privacy Policy from time to time. Changes will be posted on this page with an
        updated effective date. We encourage you to review this page periodically.
      </p>

      <h2>11. India Compliance</h2>
      <p>
        This Privacy Policy is intended to comply with the Information Technology Act, 2000 and the
        Digital Personal Data Protection Act, 2023 (DPDP Act) of India, where applicable.
      </p>

      <h2>12. Contact</h2>
      <div className="legal-contact">
        <p>
          For privacy-related questions or data requests, contact us at:{' '}
          <a href="mailto:investment.research50@gmail.com">investment.research50@gmail.com</a>
        </p>
      </div>
    </div>
  )
}
