import os
import sys
import re

from Deadline.Plugins import *
from Deadline.Scripting import *

def GetDeadlinePlugin():
    return OpenCVDistortionPlugin()

def CleanupDeadlinePlugin(deadlinePlugin):
    deadlinePlugin.Cleanup()

class OpenCVDistortionPlugin(DeadlinePlugin):
    def __init__(self):
        self.InitializeProcessCallback += self.InitializeProcess
        self.RenderExecutableCallback += self.RenderExecutable
        self.RenderArgumentCallback += self.RenderArgument

    def Cleanup(self):
        for stdoutHandler in self.StdoutHandlers:
            del stdoutHandler.Callback
        del self.InitializeProcessCallback
        del self.RenderExecutableCallback
        del self.RenderArgumentCallback

    def InitializeProcess(self):
        self.PluginType = PluginType.Simple
        self.StdoutHandling = True
        self.PopupHandling = False # Background process

        # Set UV Environment Variables based on OS
        is_windows = sys.platform.startswith("win")
        
        # job = self.GetJob() # No longer needed for these env vars

        if is_windows:
            uv_cache = self.GetConfigEntry("UVCacheDirWindows")
            uv_python = self.GetConfigEntry("UVPythonInstallDirWindows")
        else:
            uv_cache = self.GetConfigEntry("UVCacheDirLinux")
            uv_python = self.GetConfigEntry("UVPythonInstallDirLinux")
        
        if uv_cache:
            self.SetProcessEnvironmentVariable("UV_CACHE_DIR", uv_cache)
        if uv_python:
            self.SetProcessEnvironmentVariable("UV_PYTHON_INSTALL_DIR", uv_python)

        # Ensure uv executable has execute permissions (Linux/Mac)
        if not is_windows:
            plugin_dir = self.GetPluginDirectory()
            uv_exe = os.path.join(plugin_dir, "uv-linux", "uv")
            if os.path.exists(uv_exe):
                self.SetProcessEnvironmentVariable("CHMOD_UV", uv_exe) # Just a marker, actual chmod below
                # Use python's os.chmod since we can run python code here
                try:
                    import stat
                    st = os.stat(uv_exe)
                    os.chmod(uv_exe, st.st_mode | stat.S_IEXEC)
                    self.LogInfo("Set execute permission for: {}".format(uv_exe))
                except Exception as e:
                    self.LogWarning("Failed to set execute permission for {}: {}".format(uv_exe, e))

        # Add stdout handlers to capture progress from distortion.py
        self.AddStdoutHandlerCallback(".*Progress: (.*)%.*").HandleCallback += self.HandleProgress
        self.AddStdoutHandlerCallback(".*Error:.*").HandleCallback += self.HandleError

    def RenderExecutable(self):
        # Resolve bundled uv executable based on OS
        is_windows = sys.platform.startswith("win")
        plugin_dir = self.GetPluginDirectory()
        
        if is_windows:
            uv_exe = os.path.join(plugin_dir, "uv-windows", "uv.exe")
        else:
            uv_exe = os.path.join(plugin_dir, "uv-linux", "uv")
            
        return uv_exe

    def RenderArgument(self):
        # 1. Get Configuration
        # Script is now bundled with the plugin
        script_path = os.path.join(self.GetPluginDirectory(), "distortion.py")
        
        json_path = RepositoryUtils.CheckPathMapping(self.GetPluginInfoEntry("JsonPath"))
        input_pattern = RepositoryUtils.CheckPathMapping(self.GetPluginInfoEntry("InputFile"))
        output_dir = RepositoryUtils.CheckPathMapping(self.GetPluginInfoEntry("OutputDir"))
        undistort = self.GetBooleanPluginInfoEntry("Undistort")

        # 2. Determine Frame Range
        start_frame = self.GetStartFrame()
        end_frame = self.GetEndFrame()
        
        # 3. Build Arguments for 'uv run'
        # Command structure: uv run --frozen --no-dev --script <script> -- <script_args>
        arguments = [
            'run',
            '--frozen',  # Use uv.lock strictly
            '--no-dev',  # Don't install dev dependencies
            '"{}"'.format(script_path), # The script to run
            '--json_path "{}"'.format(json_path),
            '--input_pattern "{}"'.format(input_pattern),
            '--output_dir "{}"'.format(output_dir),
            '--start_frame {}'.format(start_frame),
            '--end_frame {}'.format(end_frame)
        ]

        if undistort:
            arguments.append('--undistort')

        return " ".join(arguments)

    def HandleProgress(self):
        # Optional: Parse progress if your script outputs it
        pass

    def HandleError(self):
        self.FailRender(self.GetRegexMatch(0))
