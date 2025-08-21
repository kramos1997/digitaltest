import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Search, ExternalLink, Clock, Shield, Loader2 } from "lucide-react";
import type { ResearchResult, ResearchStatus } from "@shared/research-schema";

export default function Home() {
  const [query, setQuery] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [result, setResult] = useState<ResearchResult | null>(null);
  const [status, setStatus] = useState<ResearchStatus | null>(null);

  const exampleQueries = [
    "What are the latest developments in quantum computing?",
    "How is climate change affecting European agriculture?",
    "What are the cybersecurity implications of 5G networks?"
  ];

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setResult(null);
    setStatus({ status: "starting", message: "Initializing research..." });

    try {
      // Call the actual research API
      const response = await fetch("/api/research", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          query,
          options: {
            depth: "standard",
            max_sources: 15,
            include_contact_info: false,
            research_timeout: 120
          }
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || "Research failed");
      }

      const researchResult = await response.json();
      setResult(researchResult);
      setStatus({ status: "complete", message: "Research complete!" });

    } catch (error) {
      console.error("Research error:", error);
      setStatus({ 
        status: "error", 
        message: error instanceof Error ? error.message : "Research failed. Please try again." 
      });
    } finally {
      setIsLoading(false);
    }
  };



  const useExampleQuery = (exampleQuery: string) => {
    setQuery(exampleQuery);
  };

  return (
    <div className="min-h-screen bg-[#F9F9F9]">
      {/* Header */}
      <div className="sticky top-0 bg-white/95 backdrop-blur-sm border-b border-gray-100">
        <div className="max-w-4xl mx-auto px-6 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-xl font-semibold text-[#333333]">ClarityDesk</h1>
          </div>
        </div>
      </div>

      <div className="max-w-3xl mx-auto px-6 py-12">
        {/* Search Form */}
        <div className="mb-12">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="relative">
              <Input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask a research question..."
                className="w-full h-14 text-base border-gray-200 rounded-lg focus:border-[#3B82F6] focus:ring-1 focus:ring-[#3B82F6] transition-colors"
                disabled={isLoading}
              />
              <Button 
                type="submit" 
                size="sm" 
                className="absolute right-3 top-3 bg-[#3B82F6] hover:bg-[#2563EB] border-0 rounded-md"
                disabled={isLoading || !query.trim()}
              >
                {isLoading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Search className="w-4 h-4" />
                )}
              </Button>
            </div>
          </form>

          {/* Example Queries */}
          {!result && (
            <div className="mt-8">
              <p className="text-sm text-gray-500 mb-4">Try asking:</p>
              <div className="space-y-3">
                {exampleQueries.map((example, index) => (
                  <button
                    key={index}
                    className="w-full text-left p-4 text-gray-700 hover:bg-white hover:shadow-sm rounded-lg transition-all duration-200 border border-transparent hover:border-gray-100"
                    onClick={() => useExampleQuery(example)}
                    disabled={isLoading}
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* Status Display */}
        {status && (
          <div className="mb-8">
            <div className="bg-white rounded-lg border border-gray-100 p-4">
              <div className="flex items-center gap-3">
                {status.status === "error" ? (
                  <div className="w-2 h-2 bg-red-400 rounded-full" />
                ) : status.status === "complete" ? (
                  <div className="w-2 h-2 bg-green-400 rounded-full" />
                ) : (
                  <div className="w-2 h-2 bg-[#3B82F6] rounded-full animate-pulse" />
                )}
                <span className="text-sm text-gray-600">{status.message}</span>
                {status.progress && (
                  <div className="ml-auto flex items-center gap-3">
                    <div className="w-32 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-[#3B82F6] transition-all duration-500 ease-out"
                        style={{ width: `${status.progress}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400">{status.progress}%</span>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Results */}
        {result && (
          <div className="space-y-8">
            {/* Main Answer */}
            <div className="bg-white rounded-lg border border-gray-100 p-8">
              <div className="flex items-center justify-between mb-6">
                <h2 className="text-lg font-medium text-[#333333]">Answer</h2>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Clock className="w-4 h-4" />
                  {result.research_metadata.research_time_seconds.toFixed(1)}s
                </div>
              </div>
              <div className="prose prose-gray max-w-none">
                {result.answer.split('\n').map((paragraph: string, index: number) => (
                  paragraph.trim() && (
                    <p key={index} className="mb-6 text-gray-700 leading-relaxed text-base">
                      {paragraph}
                    </p>
                  )
                ))}
              </div>
            </div>

            {/* Sources */}
            <div className="bg-white rounded-lg border border-gray-100 p-8">
              <h3 className="text-lg font-medium text-[#333333] mb-6">Sources</h3>
              <div className="space-y-6">
                {result.sources.map((source: any, index: number) => (
                  <div key={index} className="border-b border-gray-50 pb-6 last:border-b-0 last:pb-0">
                    <div className="flex items-start justify-between gap-3 mb-3">
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-[#3B82F6] hover:text-[#2563EB] text-base leading-tight flex-1 transition-colors"
                      >
                        {source.title}
                      </a>
                      <ExternalLink className="w-4 h-4 text-gray-300 mt-0.5 flex-shrink-0" />
                    </div>
                    <p className="text-sm text-gray-600 mb-3 leading-relaxed">
                      {source.key_findings}
                    </p>
                    <div className="flex items-center justify-between text-xs">
                      <span className="text-gray-400">{source.domain}</span>
                      <span className="text-gray-500">{Math.round(source.relevance_score * 100)}% relevance</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Welcome State */}
        {!result && !status && (
          <div className="text-center py-16">
            <div className="w-12 h-12 bg-gray-50 rounded-full flex items-center justify-center mx-auto mb-6">
              <Search className="w-6 h-6 text-gray-400" />
            </div>
            <h2 className="text-2xl font-medium text-[#333333] mb-4">
              Deep Research with Evidence
            </h2>
            <p className="text-gray-500 max-w-md mx-auto leading-relaxed">
              Get comprehensive answers with citations, sources, and audit-ready evidence trails. 
              GDPR-compliant research for business users.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}