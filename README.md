# YL MeshCheckHUD

**Check mesh issues directly in the Blender viewport, fix your model, and see whether the problems have been cleaned up in real time.**

Suitable for:

- Pre-delivery model checks
- Hard-surface model cleanup
- Quickly finding problematic objects in large scenes
- Checking common issues such as Ngons, overlapping vertices, non-manifold geometry, and tiny faces

---

## Language Support

- English
- 中文（简体 / 繁體）
- 日本語
- 한국어
- Deutsch
- Français
- Español
- Italiano
- Português
- Polski
- Русский
- Tiếng Việt

---

## Check Mode: Fix Models While Watching the Results

**Check Mode** is the core feature of YL MeshCheckHUD.  
It displays common topology issues directly on the model and shows the count of each issue type in the sidebar list.

You can fix the model while watching the results update, without manually refreshing the check.

Supported checks:

- Ngons
- Overlapping vertices
- Loose vertices
- Needle triangles
- Tiny faces
- Poles
- Non-manifold edges
- Missing sharp edges

<img width="800" height="500" alt="Realtime fix" src="https://github.com/user-attachments/assets/dd29aeb8-6a5f-47aa-a5d1-8e0fb1f08ca4" />

---

## Realtime HUD: View Key Mesh Information While Modeling

**Realtime HUD** displays commonly used mesh information directly in the 3D viewport, such as the triangle count and dimensions of the selected mesh. Whether you select the whole object or part of the mesh in Edit Mode, the HUD shows the result directly in the viewport.

It can display:

- Triangle count of the current model
- Dimensions of the selected object
- Statistics for multiple selected objects
- Dimensions of selected vertices, edges, or faces in Edit Mode
- Unapplied scale warning

<img width="760" height="560" alt="HUD" src="https://github.com/user-attachments/assets/79713953-e095-4ba1-8fcd-63518b500da5" />

---

## Heatmap Preview: Quickly Find Objects With Unusual Complexity

**Heatmap Preview** uses color to visualize the triangle count of objects in the scene. It also shows each object's triangle percentage, material / material slot count, and UV count in the list and HUD.

Suitable for checking:

- Object triangle count
- Triangle percentage in the scene
- Material count / material slot count
- UV count

<img width="760" height="560" alt="Heatmap" src="https://github.com/user-attachments/assets/7d9547af-4914-4fc2-a92e-87c471d25596" />

---

## Location in Blender

After installation, press `N` to open the **3D Viewport Sidebar**, then go to the **YL MeshCheckHUD** tab.

The add-on includes three main tools:

- Check Mode
- Heatmap Preview
- Realtime HUD

---

## Supported Blender Versions

- Blender **4.2** to **5.3**

---

## License

GNU General Public License v3.0
