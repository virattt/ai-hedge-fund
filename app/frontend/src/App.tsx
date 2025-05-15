import { useState } from 'react';
import { Flow } from './components/flow';
import { Layout } from './components/layout';


export default function App() {
  const [showLeftSidebar] = useState(false);
  const [showRightSidebar] = useState(false);

  return (
    <Layout
      leftSidebar={showLeftSidebar ? <div className="p-4 text-white">Left Sidebar Content</div> : undefined}
      rightSidebar={showRightSidebar ? <div className="p-4 text-white">Right Sidebar Content</div> : undefined}
    >
      <Flow />
    </Layout>
  );
}
