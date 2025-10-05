"""
Workflow visualization helper for the Agent Framework code reviewer.
Demonstrates how to visualize the review workflow.
"""
import asyncio
from agent_framework import WorkflowBuilder, WorkflowViz
from Agent_framework_agent import (
    ReviewerHandler,
    ReviewSingleDiffExecutor,
    CompleteReviewExecutor,
    Model
)
from Services.Git.git_factory import git_service_factory


async def visualize_workflow():
    """Generate and export workflow visualizations."""
    print("Generating workflow visualization...\n")

    # Load instructions
    handler = ReviewerHandler()
    instructions = await handler.load_instructions()

    # Create models
    review_model = Model(
        agent_name="CodeReviewer",
        instructions=instructions,
        model_id="gemini-2.5-flash"
    )

    summary_model = Model(
        agent_name="ReviewSummarizer",
        instructions="You are an expert at summarizing code reviews.",
        model_id="gemini-2.5-flash"
    )

    # Create executors
    git_service = git_service_factory("github")

    review_executor = ReviewSingleDiffExecutor(
        id="review_diffs",
        model=review_model,
        git_service=git_service,
        instructions=instructions
    )

    complete_executor = CompleteReviewExecutor(
        id="complete_review",
        model=summary_model
    )

    # Build workflow
    workflow = (
        WorkflowBuilder()
        .set_start_executor(review_executor)
        .add_edge(review_executor, complete_executor)
        .build()
    )

    # Create visualizer
    viz = WorkflowViz(workflow)

    # Print Mermaid diagram
    mermaid_content = viz.to_mermaid()
    print("=" * 60)
    print("MERMAID FLOWCHART")
    print("=" * 60)
    print(mermaid_content)
    print()

    # Try to export diagrams
    try:
        # Export as SVG (vector format, recommended)
        svg_file = viz.export(format="svg", filename="review_workflow")
        print(f"✓ SVG exported to: {svg_file}")

        # Export as PNG (raster format)
        png_file = viz.export(format="png", filename="review_workflow")
        print(f"✓ PNG exported to: {png_file}")

        # Export as PDF (vector format)
        pdf_file = viz.export(format="pdf", filename="review_workflow")
        print(f"✓ PDF exported to: {pdf_file}")

        # Export raw DOT file
        dot_file = viz.export(format="dot", filename="review_workflow")
        print(f"✓ DOT file exported to: {dot_file}")

        print("\nAll visualization files generated successfully!")

    except ImportError:
        print("⚠️  Image export not available.")
        print("To enable, install:")
        print("  pip install agent-framework[viz]")
        print("  And install GraphViz binaries for your platform")
        print("  (https://graphviz.org/download/)")

    except Exception as e:
        print(f"❌ Error exporting visualizations: {e}")

    print("\n" + "=" * 60)
    print("WORKFLOW DESCRIPTION")
    print("=" * 60)
    print("""
The Code Review Workflow consists of two sequential executors:

1. ReviewSingleDiffExecutor (review_diffs)
   ↓
   • Receives: ReviewState with diffs[]
   • Loops through each diff
   • For each diff:
     - Creates ReAct agent with tools:
       * get_file_content(file_path)
       * search_related_files(search_term)
     - Agent reviews the diff (can use tools for context)
     - Stores ReviewComment in state
     - Streams progress updates
   • Outputs: ReviewState with review_comments[]
   ↓
2. CompleteReviewExecutor (complete_review)
   ↓
   • Receives: ReviewState with review_comments[]
   • Analyzes all reviews
   • Generates ReviewSummary:
     - Total files reviewed
     - Files requiring rework
     - Overall assessment
     - Key issues list
   • Outputs: Final ReviewState with summary
   ↓
   [END]

Key Features:
- ReAct pattern: Agent reasons and acts (calls tools) as needed
- Structured output: Type-safe Pydantic models
- Status streaming: Real-time progress via shared state
- Autonomous context gathering: Agent decides when to fetch files
""")


def print_mermaid_only():
    """Print a simple Mermaid diagram for documentation."""
    diagram = """
graph TD
    Start([Start Review]) --> Input[ReviewState with diffs]
    Input --> Review[ReviewSingleDiffExecutor]
    
    Review --> Loop{For each diff}
    Loop --> Agent[ReAct Agent Review]
    Agent --> Tools{Need Context?}
    Tools -->|Yes| GetFile[get_file_content]
    Tools -->|Yes| Search[search_related_files]
    GetFile --> Agent
    Search --> Agent
    Tools -->|No| Store[Store ReviewComment]
    Store --> Stream[Stream Status]
    Stream --> Loop
    Loop -->|Done| Summary[CompleteReviewExecutor]
    
    Summary --> Analyze[Analyze All Reviews]
    Analyze --> Generate[Generate Summary]
    Generate --> Output[ReviewState with summary]
    Output --> End([End Review])
    
    style Review fill:#e1f5fe
    style Summary fill:#f3e5f5
    style Agent fill:#fff9c4
    style Tools fill:#ffccbc
    """

    print("=" * 60)
    print("DETAILED MERMAID DIAGRAM (Copy for use in docs)")
    print("=" * 60)
    print(diagram)


if __name__ == "__main__":
    print("\nAgent Framework Code Reviewer - Workflow Visualization\n")
    print("1. Generate workflow visualizations")
    print("2. Print Mermaid diagram only")
    print("3. Exit")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        asyncio.run(visualize_workflow())
    elif choice == "2":
        print_mermaid_only()
    elif choice == "3":
        print("Goodbye!")
    else:
        print("Invalid choice.")
