import matplotlib.pyplot as plt
import matplotlib.patches as patches
import sys
from pathlib import Path

# Add project root to sys.path to import ProjectPaths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(PROJECT_ROOT))
from scripts.paths import ProjectPaths

def draw_system_architecture():
    fig, ax = plt.subplots(figsize=(14, 9))
    ax.axis('off')

    # Draw Windows Box
    win_rect = patches.FancyBboxPatch((0.05, 0.2), 0.4, 0.6, boxstyle="round,pad=0.02",
                                      edgecolor='#2e7d32', facecolor='#e8f5e9', lw=2)
    ax.add_patch(win_rect)
    ax.text(0.25, 0.76, "Windows Environment", fontsize=16, fontweight='bold', ha='center', color='#1b5e20')
    ax.text(0.25, 0.70, "Git Clone: SIS_Analysis_Windows", fontsize=12, ha='center')
    
    # Windows internal components
    ax.add_patch(patches.Rectangle((0.1, 0.45), 0.3, 0.15, edgecolor='#1565c0', facecolor='#bbdefb', lw=1.5))
    ax.text(0.25, 0.55, "High-Volume Data", fontsize=12, fontweight='bold', ha='center')
    ax.text(0.25, 0.50, "data/ & figures/\n(Tracked by DVC)", fontsize=10, ha='center')

    ax.add_patch(patches.Rectangle((0.1, 0.25), 0.3, 0.15, edgecolor='#d84315', facecolor='#ffccbc', lw=1.5))
    ax.text(0.25, 0.35, "DVC Management", fontsize=12, fontweight='bold', ha='center')
    ax.text(0.25, 0.30, "dvc add / dvc pull / dvc push", fontsize=10, ha='center')

    # Draw WSL Box
    wsl_rect = patches.FancyBboxPatch((0.55, 0.2), 0.4, 0.6, boxstyle="round,pad=0.02",
                                      edgecolor='#ef6c00', facecolor='#fff3e0', lw=2)
    ax.add_patch(wsl_rect)
    ax.text(0.75, 0.76, "WSL Environment", fontsize=16, fontweight='bold', ha='center', color='#e65100')
    ax.text(0.75, 0.70, "Git Clone: SIS_Analysis_WSL", fontsize=12, ha='center')

    # WSL internal components
    ax.add_patch(patches.Rectangle((0.6, 0.45), 0.3, 0.15, edgecolor='#4527a0', facecolor='#d1c4e9', lw=1.5))
    ax.text(0.75, 0.55, "Data Processing & Analysis", fontsize=12, fontweight='bold', ha='center')
    ax.text(0.75, 0.50, "Conda: sis_analysis\ndvc repro / jupyter notebook", fontsize=10, ha='center')
    
    ax.add_patch(patches.Rectangle((0.6, 0.25), 0.3, 0.15, edgecolor='#c62828', facecolor='#ffcdd2', lw=1.5))
    ax.text(0.75, 0.35, "Code & Scripts", fontsize=12, fontweight='bold', ha='center')
    ax.text(0.75, 0.30, "notebooks/ & scripts/\n(Tracked by Git)", fontsize=10, ha='center')

    # Arrows for Git and Symlink
    # Symlink Arrow connecting Windows 'High-Volume Data' and WSL 'Data Processing'
    ax.annotate("", xy=(0.4, 0.525), xytext=(0.6, 0.525),
                arrowprops=dict(arrowstyle="<->", color="black", lw=2, ls='dashed'))
    ax.text(0.5, 0.54, "Symlinks\n(Direct File Access)", fontsize=10, ha='center', va='bottom', fontweight='bold')

    # Git remote box (top middle)
    ax.add_patch(patches.Rectangle((0.4, 0.85), 0.2, 0.1, edgecolor='black', facecolor='#f5f5f5', lw=1.5))
    ax.text(0.5, 0.9, "Git Remote\n(GitHub)", fontsize=12, fontweight='bold', ha='center', va='center')

    # Git arrows
    ax.annotate("", xy=(0.4, 0.9), xytext=(0.25, 0.82),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=2))
    ax.annotate("", xy=(0.6, 0.9), xytext=(0.75, 0.82),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=2))
    
    ax.text(0.31, 0.87, "git push/pull", fontsize=10, ha='center', rotation=30)
    ax.text(0.69, 0.87, "git push/pull", fontsize=10, ha='center', rotation=-30)

    # DVC Remote
    ax.add_patch(patches.Rectangle((0.4, 0.05), 0.2, 0.1, edgecolor='black', facecolor='#f5f5f5', lw=1.5))
    ax.text(0.5, 0.1, "DVC Remote Storage\n(e.g., S3 / GDrive)", fontsize=11, fontweight='bold', ha='center', va='center')

    # DVC Arrow
    ax.annotate("", xy=(0.4, 0.1), xytext=(0.25, 0.18),
                arrowprops=dict(arrowstyle="<->", color="gray", lw=2))
    
    ax.text(0.31, 0.13, "dvc push/pull", fontsize=10, ha='center', rotation=-30)

    # WSL dvc pull hint
    ax.annotate("", xy=(0.6, 0.1), xytext=(0.75, 0.18),
                arrowprops=dict(arrowstyle="<-", color="gray", lw=1.5, ls='dotted'))
    ax.text(0.69, 0.13, "dvc pull\n(optional)", fontsize=10, ha='center', rotation=30)

    plt.title("SIS_Analysis Hybrid Workflow Architecture", fontsize=20, fontweight='bold', pad=30)
    
    # Save the figure
    out_dir = ProjectPaths.FIGURES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "workflow_architecture.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight', facecolor='white')
    print(f"Workflow architecture diagram saved to {out_path}")

if __name__ == "__main__":
    draw_system_architecture()
