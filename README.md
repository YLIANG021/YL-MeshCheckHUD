# YL MeshCheckHUD

YL MeshCheckHUD is a Blender addon for live mesh stats, heatmap analysis, and viewport mesh checking.

It helps you inspect triangle count, dimensions, mesh density, and common topology issues directly inside the 3D View.

## Features

- Live HUD for triangle count and dimensions
- Multi-object and partial mesh selection support
- Heatmap preview for mesh complexity
- Ranked object list with sorting
- Viewport mesh checks with colored overlays
- Real-time issue inspection while modeling
- Optional X-Ray check overlay
- Multi-language UI support

## Mesh Checks

YL MeshCheckHUD can highlight common mesh issues such as:

- Ngons
- Doubles
- Isolated vertices
- Needle triangles
- Tiny faces
- Poles
- Non-manifold edges
- Missing sharp edges

## Supported Blender Versions

- Blender 4.2 to 5.2

## Supported Platforms

- Windows x86_64
- macOS arm64
- macOS x86_64
- Linux x86_64

## Installation

1. Download the addon package.
2. In Blender, go to `Edit > Preferences > Add-ons`.
3. Click the dropdown in the top-right corner and choose `Install from Disk`.
4. Select the addon `.zip` file.
5. Enable `YL MeshCheckHUD`.

## Usage

### Live HUD

- Select one or more mesh objects to see live triangle count and dimensions.
- In Edit Mode, selected mesh elements can also be measured in real time.
- The HUD can warn you about unapplied scale.

### Heatmap Preview

- Switch to `Preview` mode.
- Enable the heatmap to compare mesh complexity across objects.
- Warmer colors indicate heavier meshes, while cooler colors indicate lighter meshes.
- Results can be sorted from the list.

### Check Mode

- Switch to `Check` mode.
- Enable the checks you want to display.
- Issues are drawn directly in the viewport with different colors.
- You can sort the results list and isolate the checks you care about.

## Repository

- GitHub: https://github.com/YLIANG021/YL-MeshCheckHUD

## License

This addon is licensed under:

- GPL-3.0-or-later
