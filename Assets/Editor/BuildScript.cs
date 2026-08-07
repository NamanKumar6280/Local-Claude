using UnityEditor;
using UnityEngine;
using System.Linq;

public static class BuildScript
{
    [MenuItem("Build/Build Android")]
    public static void BuildAndroid()
    {
        BuildPlayerOptions buildOptions = new BuildPlayerOptions
        {
            scenes = EditorBuildSettings.scenes.Where(scene => scene.enabled).Select(scene => scene.path).ToArray(),
            locationPathName = "build/Android/HorrorGame.apk",
            target = BuildTarget.Android,
            options = BuildOptions.None
        };
        BuildPipeline.BuildPlayer(buildOptions);
        Debug.Log("APK built successfully!");
    }
}
