# Agent Framework Code Reviewer - Visual Architecture

## Complete System Diagram

```mermaid
graph TB
    Start([User Initiates Review]) --> Handler[ReviewerHandler]
    Handler --> LoadInst[Load Instructions]
    LoadInst --> FetchPR[Fetch PR Data from GitHub]
    FetchPR --> InitState[Initialize ReviewState]

    InitState --> Workflow[Agent Framework Workflow]

    subgraph Workflow[" "]
        style Workflow fill:#e3f2fd

        Review[ReviewSingleDiffExecutor]
        Review --> Loop{For Each Diff}

        Loop --> Agent[ReAct Agent]

        subgraph AgentProcess[" "]
            style AgentProcess fill:#fff9c4
            Agent --> Reason{Reasoning}
            Reason -->|Need Context?| Tools[Call Tools]
            Reason -->|Have Info| Generate[Generate Review]

            Tools --> GetFile[get_file_content]
            Tools --> Search[search_related_files]
            GetFile --> Agent
            Search --> Agent
        end

        Generate --> Store[Store ReviewComment]
        Store --> Stream[Stream Status Update]
        Stream --> Loop

        Loop -->|Done| Complete[CompleteReviewExecutor]
        Complete --> Summarize[Analyze All Reviews]
        Summarize --> Summary[Generate ReviewSummary]
    end

    Summary --> Output[Return Final State]
    Output --> Display[Display Results]

    style Start fill:#c8e6c9
    style Handler fill:#bbdefb
    style Review fill:#e1f5fe
    style Complete fill:#f3e5f5
    style Agent fill:#fff59d
    style Output fill:#c8e6c9
    style Display fill:#a5d6a7
```

## Detailed Component Breakdown

```mermaid
graph LR
    subgraph Input[Input Layer]
        User[User Request]
        Repo[repo_name]
        PR[pr_number]
    end

    subgraph Core[Core Components]
        Handler[ReviewerHandler]
        Model[Model + ChatAgent]
        Git[GitHubService]
    end

    subgraph Workflow[Workflow Layer]
        Exec1[ReviewSingleDiffExecutor]
        Exec2[CompleteReviewExecutor]
    end

    subgraph Tools[Tool Layer]
        Tool1[get_file_content]
        Tool2[search_related_files]
        Tool3[Custom Tools...]
    end

    subgraph Output[Output Layer]
        State[ReviewState]
        Comments[ReviewComments]
        Summary[ReviewSummary]
    end

    User --> Handler
    Repo --> Handler
    PR --> Handler

    Handler --> Model
    Handler --> Git
    Handler --> Exec1
    Handler --> Exec2

    Exec1 --> Tool1
    Exec1 --> Tool2
    Exec1 --> Tool3

    Exec1 --> State
    Exec2 --> State

    State --> Comments
    State --> Summary

    style Handler fill:#64b5f6
    style Model fill:#81c784
    style Git fill:#ffb74d
    style Exec1 fill:#ba68c8
    style Exec2 fill:#ba68c8
    style State fill:#4db6ac
```

## State Flow Diagram

```mermaid
stateDiagram-v2
    [*] --> Initializing: run(repo, pr_num)

    Initializing --> LoadingInstructions
    LoadingInstructions --> FetchingPR
    FetchingPR --> CreatingState

    CreatingState --> Reviewing: ReviewState with diffs

    state Reviewing {
        [*] --> ProcessingDiff
        ProcessingDiff --> AgentThinking
        AgentThinking --> NeedContext: Needs more info
        AgentThinking --> GeneratingReview: Has enough info
        NeedContext --> CallingTools
        CallingTools --> AgentThinking
        GeneratingReview --> StoringReview
        StoringReview --> StreamingStatus
        StreamingStatus --> ProcessingDiff: More diffs
        StreamingStatus --> [*]: All done
    }

    Reviewing --> Summarizing: All reviews complete

    state Summarizing {
        [*] --> AnalyzingReviews
        AnalyzingReviews --> GeneratingSummary
        GeneratingSummary --> [*]
    }

    Summarizing --> Complete
    Complete --> [*]: Return ReviewState
```

## Data Flow Diagram

```mermaid
graph TB
    subgraph External[External Services]
        GitHub[GitHub API]
        Gemini[Gemini LLM]
    end

    subgraph Input[Input Data]
        RepoName[repo_name: str]
        PRNumber[pr_number: int]
    end

    subgraph Processing[Processing Pipeline]
        Fetch[Fetch PR Diffs]
        Parse[Parse Diffs]
        Review[ReAct Agent Review]
        Store[Store Reviews]
        Analyze[Analyze All]
        Generate[Generate Summary]
    end

    subgraph Output[Output Data]
        Comments[List of ReviewComment]
        Summary[ReviewSummary]
        State[Final ReviewState]
    end

    RepoName --> Fetch
    PRNumber --> Fetch
    GitHub --> Fetch

    Fetch --> Parse
    Parse --> Review

    Review --> Gemini
    Gemini --> Review
    GitHub --> Review

    Review --> Store
    Store --> Comments

    Comments --> Analyze
    Analyze --> Generate
    Gemini --> Generate

    Generate --> Summary
    Summary --> State
    Comments --> State

    style GitHub fill:#f0f0f0
    style Gemini fill:#f0f0f0
    style State fill:#c8e6c9
```

## Class Hierarchy

```mermaid
classDiagram
    class BaseModelExecutor {
        +id: str
        +model: Model
        +handle(state, ctx)
    }

    class Model {
        +chat_client: OpenAIChatClient
        +agent: ChatAgent
    }

    class ReviewSingleDiffExecutor {
        +git_service: AbstractGitService
        +instructions: str
        +handle(state, ctx)
    }

    class CompleteReviewExecutor {
        +handle(state, ctx)
    }

    class ReviewTools {
        +git_service: AbstractGitService
        +repo_name: str
        +pr_number: int
        +get_file_content(path)
        +search_related_files(term)
        +get_tools()
    }

    class ReviewState {
        +repo_name: str
        +pr_number: int
        +diffs: List
        +review_comments: List
        +summary: ReviewSummary
    }

    class ReviewComment {
        +file_name: str
        +review_comment: str
        +requires_rework: bool
        +suggested_improvements_markdown: str
    }

    class ReviewSummary {
        +total_files_reviewed: int
        +files_requiring_rework: int
        +overall_assessment: str
        +key_issues: List
    }

    class ReviewerHandler {
        +model_id: str
        +git_service: AbstractGitService
        +load_instructions()
        +run(repo_name, pr_number)
    }

    BaseModelExecutor <|-- ReviewSingleDiffExecutor
    BaseModelExecutor <|-- CompleteReviewExecutor

    ReviewSingleDiffExecutor --> ReviewTools: uses
    ReviewSingleDiffExecutor --> Model: has
    CompleteReviewExecutor --> Model: has

    ReviewerHandler --> ReviewSingleDiffExecutor: creates
    ReviewerHandler --> CompleteReviewExecutor: creates
    ReviewerHandler --> ReviewState: manages

    ReviewState --> ReviewComment: contains many
    ReviewState --> ReviewSummary: contains one
```

## Sequence Diagram - Review Flow

```mermaid
sequenceDiagram
    participant User
    participant Handler as ReviewerHandler
    participant Git as GitHubService
    participant Workflow
    participant Executor as ReviewSingleDiffExecutor
    participant Agent as ReAct Agent
    participant Tools
    participant LLM as Gemini

    User->>Handler: run(repo, pr_num)
    Handler->>Handler: load_instructions()
    Handler->>Git: get_pull_request()
    Git-->>Handler: PR data with diffs

    Handler->>Workflow: build workflow
    Handler->>Workflow: run_stream(initial_state)

    loop For each diff
        Workflow->>Executor: handle(state)
        Executor->>Agent: run(review_prompt)

        alt Agent needs context
            Agent->>Tools: get_file_content(path)
            Tools->>Git: fetch file
            Git-->>Tools: file content
            Tools-->>Agent: content
            Agent->>Agent: continue reasoning
        end

        Agent->>LLM: generate review
        LLM-->>Agent: ReviewComment
        Agent-->>Executor: review result
        Executor->>Executor: store review
        Executor->>Workflow: stream status
    end

    Workflow->>Executor: complete review
    Executor->>Agent: summarize all reviews
    Agent->>LLM: generate summary
    LLM-->>Agent: ReviewSummary
    Agent-->>Executor: summary result

    Executor-->>Workflow: final state
    Workflow-->>Handler: ReviewState
    Handler-->>User: result
```

## Tool Interaction Pattern

```mermaid
graph TB
    Start[Agent Receives Review Request] --> Analyze[Analyze Diff]
    Analyze --> Decision{Need More Info?}

    Decision -->|Yes| SelectTool[Select Appropriate Tool]
    Decision -->|No| Generate[Generate Review]

    SelectTool --> Tool1{get_file_content?}
    SelectTool --> Tool2{search_related_files?}
    SelectTool --> Tool3{Custom tool?}

    Tool1 -->|Execute| Fetch[Fetch File from PR]
    Tool2 -->|Execute| Search[Search PR Files]
    Tool3 -->|Execute| Custom[Execute Custom Logic]

    Fetch --> Return1[Return Content]
    Search --> Return2[Return Matches]
    Custom --> Return3[Return Result]

    Return1 --> Analyze
    Return2 --> Analyze
    Return3 --> Analyze

    Generate --> Format[Format as ReviewComment]
    Format --> Output[Return Structured Output]

    style Start fill:#c8e6c9
    style Decision fill:#fff9c4
    style Generate fill:#e1f5fe
    style Output fill:#a5d6a7
```

## Copy these diagrams into documentation or use with Mermaid Live Editor:

## https://mermaid.live/
