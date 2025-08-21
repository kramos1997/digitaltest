import type { Express } from "express";
import { createServer, type Server } from "http";
import { spawn } from "child_process";
import path from "path";
import { storage } from "./storage";

export async function registerRoutes(app: Express): Promise<Server> {
  // Research API endpoint
  app.post("/api/research", async (req, res) => {
    try {
      const { query, options = {} } = req.body;
      
      if (!query || typeof query !== 'string') {
        return res.status(400).json({ error: "Query is required and must be a string" });
      }

      // Set default options
      const researchOptions = {
        depth: options.depth || "standard",
        max_sources: options.max_sources || 20,
        include_contact_info: options.include_contact_info || false,
        research_timeout: options.research_timeout || 300
      };

      console.log(`🔍 Starting research for: "${query}"`);

      // Create the Python script path
      const scriptPath = path.join(process.cwd(), "server", "research_runner.py");
      
      // Prepare the request data
      const requestData = {
        query,
        options: researchOptions
      };

      // Spawn Python process
      const pythonProcess = spawn("python3", [scriptPath], {
        stdio: ["pipe", "pipe", "pipe"],
        env: process.env
      });

      let output = "";
      let error = "";

      // Send request data to Python process
      pythonProcess.stdin.write(JSON.stringify(requestData));
      pythonProcess.stdin.end();

      // Collect output
      pythonProcess.stdout.on("data", (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on("data", (data) => {
        error += data.toString();
        console.error("Python error:", data.toString());
      });

      pythonProcess.on("close", (code) => {
        if (code !== 0) {
          console.error("Python process failed with code:", code);
          console.error("Error output:", error);
          return res.status(500).json({ 
            error: "Research process failed",
            details: error || "Unknown error occurred"
          });
        }

        try {
          const result = JSON.parse(output);
          res.json(result);
        } catch (parseError) {
          console.error("Failed to parse Python output:", parseError);
          console.error("Raw output:", output);
          res.status(500).json({ 
            error: "Failed to parse research results",
            details: parseError.message
          });
        }
      });

      // Handle timeout
      const timeout = setTimeout(() => {
        pythonProcess.kill();
        res.status(408).json({ error: "Research request timed out" });
      }, researchOptions.research_timeout * 1000);

      pythonProcess.on("close", () => {
        clearTimeout(timeout);
      });

    } catch (error) {
      console.error("Research endpoint error:", error);
      res.status(500).json({ error: "Internal server error", details: error.message });
    }
  });

  // Health check endpoint
  app.get("/api/health", (req, res) => {
    res.json({ status: "ok", timestamp: new Date().toISOString() });
  });

  const httpServer = createServer(app);
  return httpServer;
}
