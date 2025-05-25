import { HedgeFund } from './components/HedgeFund';

function App() {
    return (
        <div className="min-h-screen bg-gray-50">
            <header className="bg-white shadow">
                <div className="container mx-auto px-4 py-6">
                    <h1 className="text-2xl font-bold text-gray-900">AI Hedge Fund</h1>
                </div>
            </header>
            <main>
                <HedgeFund />
            </main>
        </div>
    );
}

export default App;
