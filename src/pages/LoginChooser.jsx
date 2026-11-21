import Crumbs from '../components/Crumbs'
import RoleCards from '../components/RoleCards'

export default function LoginChooser() {
  return (
    <>
      <Crumbs trail={[['Login']]} />
      <h1>Login</h1>
      <p className="lead">
        Choose how you use the portal. Each role signs in differently, and sees only what it needs.
      </p>
      <RoleCards heading="Sign in as" />
    </>
  )
}
