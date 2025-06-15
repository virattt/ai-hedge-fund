// app/next-frontend/app/page.tsx
import { redirect } from 'next/navigation';

export default function HomePage() {
  redirect('/dashboard');
  // Or, return a simpler landing page if preferred before redirection
  // return (
  //   <div className="flex flex-col items-center justify-center min-h-screen">
  //     <h1 className="text-2xl font-bold">Loading Financial Platform...</h1>
  //   </div>
  // );
}
