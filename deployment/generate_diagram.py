import matplotlib.pyplot as plt
import matplotlib.patches as patches

def create_architecture_diagram(output_file="financial-advisor.png"):
    fig, ax = plt.subplots(figsize=(10, 12))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 14)
    ax.axis('off')

    # Define box properties
    box_width = 8
    box_height = 1.5
    x_start = 1
    y_start = 12
    gap = 0.5

    layers = [
        ("Layer 1: Syntax Trapdoor", "Pydantic Models\n(Schema Validation)", "#E6F3FF", "#0052CC"),
        ("Layer 2: Policy Engine", "Open Policy Agent (OPA)\n(RBAC & Allow/Deny)", "#E6FFFA", "#006644"),
        ("Layer 3: Semantic Verifier", "Verifier Agent\n(Intent & Risk Analysis)", "#FFF0B3", "#B38600"),
        ("Layer 4: Consensus Engine", "Multi-Agent Debate\n(High-Stakes Voting)", "#FFD6E8", "#990055"),
        ("Layer 5: Human-in-the-Loop", "Escalation Queue\n(Constructive Friction)", "#E3DFFF", "#403294"),
        ("Layer 6: Ephemeral Isolation", "Sandboxing (Physics)\n(Blast Radius Containment)", "#FFEBE6", "#BF2600")
    ]

    # Draw layers
    current_y = y_start
    for title, desc, bg_color, border_color in layers:
        # Box
        rect = patches.FancyBboxPatch(
            (x_start, current_y - box_height), box_width, box_height,
            boxstyle="round,pad=0.1",
            linewidth=2,
            edgecolor=border_color,
            facecolor=bg_color
        )
        ax.add_patch(rect)

        # Text
        ax.text(
            x_start + box_width/2, current_y - box_height/2 + 0.3,
            title,
            ha='center', va='center', fontsize=14, fontweight='bold', color=border_color
        )
        ax.text(
            x_start + box_width/2, current_y - box_height/2 - 0.3,
            desc,
            ha='center', va='center', fontsize=12, color='#333333'
        )

        # Arrow (except for last layer)
        if current_y > y_start - (len(layers)-1) * (box_height + gap):
             ax.arrow(
                x_start + box_width/2, current_y - box_height,
                0, -gap + 0.1,
                head_width=0.2, head_length=0.2, fc='black', ec='black'
            )

        current_y -= (box_height + gap)

    plt.title("Cybernetic Governance Architecture (6-Layer Stack)", fontsize=16, fontweight='bold', pad=20)
    plt.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Diagram saved to {output_file}")

if __name__ == "__main__":
    create_architecture_diagram()
