// Put this file in Assets/Editor/. Usage:
// Unity -batchmode -nographics -quit -projectPath . -logFile build.log \
//   -executeMethod Gamesmith.BuildScript.BuildFromCommandLine \
//   -buildTarget Win64 -target StandaloneWindows64 -out Builds/Win/Game.exe [-development]
// -buildTarget (Unity's own flag: Win64, OSXUniversal, Linux64, Android, iOS, WebGL) opens the
// project directly on that platform; -target (a BuildTarget enum name) is what gets built.
using System;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.Build.Reporting;
using UnityEngine;

namespace Gamesmith
{
    public static class BuildScript
    {
        public static void BuildFromCommandLine()
        {
            string[] args = Environment.GetCommandLineArgs();
            string outPath = Arg(args, "-out") ?? "Builds/Game";
            string targetName = Arg(args, "-target");
            bool development = args.Contains("-development");

            BuildTarget target = EditorUserBuildSettings.activeBuildTarget;
            if (!string.IsNullOrEmpty(targetName) && !Enum.TryParse(targetName, true, out target))
            {
                Fail($"Unknown -target '{targetName}'.");
                return;
            }

            string[] scenes = EditorBuildSettings.scenes
                .Where(s => s.enabled)
                .Select(s => s.path)
                .ToArray();
            if (scenes.Length == 0)
            {
                Fail("No enabled scenes in File > Build Settings.");
                return;
            }

            string dir = Path.GetDirectoryName(Path.GetFullPath(outPath));
            if (!string.IsNullOrEmpty(dir)) Directory.CreateDirectory(dir);

            var options = new BuildPlayerOptions
            {
                scenes = scenes,
                locationPathName = outPath,
                target = target,
                options = development ? BuildOptions.Development : BuildOptions.None,
            };

            Debug.Log($"[Gamesmith] Building {target} -> {outPath} ({scenes.Length} scenes)");
            BuildReport report = BuildPipeline.BuildPlayer(options);
            BuildSummary summary = report.summary;
            Debug.Log($"[Gamesmith] Result: {summary.result}, size: {summary.totalSize / (1024 * 1024)} MB, " +
                      $"errors: {summary.totalErrors}, warnings: {summary.totalWarnings}, time: {summary.totalTime}");

            if (summary.result != BuildResult.Succeeded)
            {
                Fail($"Build {summary.result}.");
                return;
            }
            EditorApplication.Exit(0);
        }

        static string Arg(string[] args, string name)
        {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }

        static void Fail(string message)
        {
            Debug.LogError("[Gamesmith] " + message);
            EditorApplication.Exit(1);
        }
    }
}
