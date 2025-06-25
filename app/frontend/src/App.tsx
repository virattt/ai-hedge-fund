
import { Flow } from './components/flow';
import { Layout } from './components/layout';
import { Toaster } from './components/ui/sonner';


export default function App() {
  return (
    <>
      <Layout>
        <Flow />
      </Layout>
      <Toaster />
    </>
  );
}
