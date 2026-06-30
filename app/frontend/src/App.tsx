import { Layout } from './components/Layout';
import { BetaLayout } from './components/BetaLayout';
import { LoginGate } from './components/LoginGate';
import { Toaster } from './components/ui/sonner';

const BETA_MODE = import.meta.env.VITE_BETA_MODE !== 'false';

export default function App() {
  if (BETA_MODE) {
    return (
      <>
        <LoginGate>
          <BetaLayout />
        </LoginGate>
        <Toaster />
      </>
    );
  }

  return (
    <>
      <Layout><></></Layout>
      <Toaster />
    </>
  );
}
