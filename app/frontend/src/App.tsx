import { useState } from 'react';
import { Flow } from './components/Flow';
import { Layout } from './components/Layout';

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
