# Vellum Language Specification

**Version**: 1.0.0-draft
**Status**: LegiVellum Integration
**Purpose**: The specification language for LegiVellum - deterministic, cross-platform, receipt-driven AI coordination

---

## 1. Overview

### 1.1 What is Vellum?

Vellum is the specification language for the LegiVellum ecosystem. It provides:

- A **semantic intermediate representation** for AI agent tasks
- **Explicit contracts** with pre/post conditions that map to receipt phases
- **Capability declarations** that map to LegiVellum's escalation system
- **Deterministic translation** to executable code in any target language
- **Type-safe semantics** where primitive types are foundational

The name "Vellum" reflects its role as the writing surface for LegiVellum - the authoritative record of intent that produces receipts.

### 1.2 Design Goals

1. **Explicit contracts** - All requirements, capabilities, inputs, outputs, and assumptions must be stated explicitly
2. **Readable by inspection** - Anyone who knows code should understand it immediately without learning the language
3. **Deterministic translation** - The same specification produces functionally identical code in any target language
4. **Type-safe semantics** - Primitive types are the foundation; vocabulary maps to typed operations
5. **No ambiguity** - Each word has exactly one meaning; domain terms must be explicitly defined
6. **Receipt-native** - First-class integration with LegiVellum's receipt protocol

### 1.3 LegiVellum Integration

Vellum is designed to work with LegiVellum's seven primitives:

| Primitive | Vellum Role |
|-----------|-------------|
| **CogniGate** | Reasons about Vellum specs, validates contracts |
| **DeleGate** | Plans written in Vellum become structured obligations |
| **MemoryGate** | Stores Vellum definitions, concepts, patterns |
| **AsyncGate** | Executes Vellum-defined tasks with lease management |
| **DepotGate** | Stores artifacts produced by Vellum procedures |
| **MetaGate** | Bootstraps Vellum modules and topology |
| **Receipts** | Vellum contracts map directly to receipt phases |

### 1.4 What Vellum Is Not

- Not executable directly (it compiles/translates to target languages)
- Not a natural language parser (strict syntax, not arbitrary English)
- Not a programming language with its own runtime

---

## 2. Primitive Types

These are the foundational types. All operations are defined in terms of these types.

### 2.1 Core Types

```
Scalar<K>         Atomic value of kind K
                  Kinds: Numeric, Integer, Decimal, String, Boolean,
                         DateTime, Duration, Identifier, ULID

Collection<T>     Ordered sequence of elements of type T
                  May contain duplicates
                  Supports: filter, map, reduce, find, sort, group

Set<T>            Unordered unique elements of type T
                  No duplicates allowed
                  Supports: filter, map, union, intersect, difference

Map<K, V>         Key-value associations
                  Supports: lookup, insert, remove, keys, values

Option<T>         A value that may or may not exist
                  Either: some(T) or none

Result<T, E>      An operation outcome
                  Either: success(T) or failure(E)

Predicate<T>      A condition over T
                  Signature: T → Boolean

Mapping<T, U>     A transformation from T to U
                  Signature: T → U

Reducer<T, A>     An accumulation operation
                  Signature: (A, T) → A

Record            Named product type (like struct)
                  Fields with types

Enum              Named sum type
                  Variants, optionally with associated data
```

### 2.2 Concurrency Types

```
Future<T>         A value that will be available later
                  Represents a single async computation

Task<T, E>        A computation that may succeed or fail asynchronously
                  Signature: () → Future<Result<T, E>>

Stream<T>         A sequence of values arriving over time
                  Supports: filter, map, take, skip, merge, zip

Channel<T>        A communication primitive between concurrent tasks
                  Supports: send, receive
```

### 2.3 LegiVellum Types

```
Receipt           Immutable proof-of-obligation record
                  Fields: receipt_id, task_id, phase, status, etc.

Phase             Receipt lifecycle phase
                  Values: accepted, complete, escalate

Status            Task completion status
                  Values: NA, success, failure, canceled

EscalationClass   Reason for escalation
                  Values: NA, owner, capability, trust, policy, scope, other

OutcomeKind       Type of task output
                  Values: NA, none, response_text, artifact_pointer, mixed

Principal         Identity that can create obligations
                  Format: dot-notation (e.g., "delegate.primary")

Lease<T>          Time-bounded claim on a task
                  Fields: lease_id, task_id, worker_id, expires_at

Artifact          Material output stored in DepotGate
                  Fields: pointer, location, mime_type
```

### 2.4 Type Modifiers

```
Mutable<T>        Value that can be reassigned
Ref<T>            Reference to T (does not own)
Owned<T>          Exclusive ownership of T
Shared<T>         Shared reference to T
```

### 2.5 Type Parameters (Generics)

Type parameters allow definitions to work across multiple types:

```
<T>               Single type parameter
<T, U>            Multiple type parameters
<T: Constraint>   Bounded type parameter
<T: A + B>        Multiple constraints
```

### 2.6 Type Constraints

```
where T: Numeric          T must be a numeric type
where T: Comparable       T must support ordering
where T: Equatable        T must support equality
where T: Hashable         T must support hashing
where T: Sendable         T can be sent across task boundaries
where T: Cloneable        T can be duplicated
where T: Serializable     T can be serialized for receipts
```

---

## 3. Type Operations

Operations are defined by their type signatures. The vocabulary (Section 4) maps natural language to these operations.

### 3.1 Collection Operations

```
filter      : Collection<T> × Predicate<T> → Collection<T>
map         : Collection<T> × Mapping<T, U> → Collection<U>
flat_map    : Collection<T> × Mapping<T, Collection<U>> → Collection<U>
reduce      : Collection<T> × Reducer<T, A> × A → A
find        : Collection<T> × Predicate<T> → Option<T>
find_all    : Collection<T> × Predicate<T> → Collection<T>
any         : Collection<T> × Predicate<T> → Boolean
all         : Collection<T> × Predicate<T> → Boolean
none_match  : Collection<T> × Predicate<T> → Boolean
sort        : Collection<T> × Ordering<T> → Collection<T>
group       : Collection<T> × Mapping<T, K> → Map<K, Collection<T>>
partition   : Collection<T> × Predicate<T> → (Collection<T>, Collection<T>)
take        : Collection<T> × Integer → Collection<T>
skip        : Collection<T> × Integer → Collection<T>
first       : Collection<T> → Option<T>
last        : Collection<T> → Option<T>
count       : Collection<T> → Integer
is_empty    : Collection<T> → Boolean
concat      : Collection<T> × Collection<T> → Collection<T>
unique      : Collection<T> → Set<T>  where T: Equatable
zip         : Collection<T> × Collection<U> → Collection<(T, U)>
```

### 3.2 Numeric Aggregations

```
sum         : Collection<T> → T                where T: Numeric
product     : Collection<T> → T                where T: Numeric
mean        : Collection<T> → Decimal          where T: Numeric
min         : Collection<T> → Option<T>        where T: Comparable
max         : Collection<T> → Option<T>        where T: Comparable
```

### 3.3 Option Operations

```
unwrap      : Option<T> → T                    (fails if none)
unwrap_or   : Option<T> × T → T                (default if none)
map         : Option<T> × Mapping<T, U> → Option<U>
filter      : Option<T> × Predicate<T> → Option<T>
is_some     : Option<T> → Boolean
is_none     : Option<T> → Boolean
```

### 3.4 Result Operations

```
unwrap      : Result<T, E> → T                 (fails if failure)
unwrap_or   : Result<T, E> × T → T
map         : Result<T, E> × Mapping<T, U> → Result<U, E>
map_error   : Result<T, E> × Mapping<E, F> → Result<T, F>
with_context: Result<T, E> × Context → Result<T, ContextualError<E>>
is_success  : Result<T, E> → Boolean
is_failure  : Result<T, E> → Boolean
```

### 3.5 Future Operations

```
await       : Future<T> → T                    (blocks until complete)
map         : Future<T> × Mapping<T, U> → Future<U>
flat_map    : Future<T> × Mapping<T, Future<U>> → Future<U>
race        : Collection<Future<T>> → Future<T>
all         : Collection<Future<T>> → Future<Collection<T>>
timeout     : Future<T> × Duration → Future<Result<T, TimeoutError>>
```

### 3.6 Stream Operations

```
filter      : Stream<T> × Predicate<T> → Stream<T>
map         : Stream<T> × Mapping<T, U> → Stream<U>
take        : Stream<T> × Integer → Stream<T>
take_while  : Stream<T> × Predicate<T> → Stream<T>
skip        : Stream<T> × Integer → Stream<T>
merge       : Stream<T> × Stream<T> → Stream<T>
zip         : Stream<T> × Stream<U> → Stream<(T, U)>
buffer      : Stream<T> × Integer → Stream<Collection<T>>
throttle    : Stream<T> × Duration → Stream<T>
collect     : Stream<T> → Future<Collection<T>>
```

### 3.7 Receipt Operations

```
emit_accepted   : TaskDefinition → Receipt     (creates obligation)
emit_complete   : Receipt × Outcome → Receipt  (resolves obligation)
emit_escalate   : Receipt × Escalation → Receipt (transfers responsibility)
query_inbox     : Principal → Collection<Receipt>
query_timeline  : TaskId → Collection<Receipt>
```

### 3.8 Comparison Operations

```
equals      : T × T → Boolean                  where T: Equatable
less_than   : T × T → Boolean                  where T: Comparable
greater_than: T × T → Boolean                  where T: Comparable
between     : T × T × T → Boolean              where T: Comparable
```

### 3.9 Logical Operations

```
and         : Boolean × Boolean → Boolean
or          : Boolean × Boolean → Boolean
not         : Boolean → Boolean
```

### 3.10 Arithmetic Operations

```
add         : Numeric × Numeric → Numeric
subtract    : Numeric × Numeric → Numeric
multiply    : Numeric × Numeric → Numeric
divide      : Numeric × Numeric → Result<Numeric, DivisionError>
modulo      : Integer × Integer → Integer
power       : Numeric × Numeric → Numeric
negate      : Numeric → Numeric
absolute    : Numeric → Numeric
```

### 3.11 String Operations

```
concat      : String × String → String
length      : String → Integer
substring   : String × Integer × Integer → String
contains    : String × String → Boolean
starts_with : String × String → Boolean
ends_with   : String × String → Boolean
trim        : String → String
lowercase   : String → String
uppercase   : String → String
split       : String × String → Collection<String>
join        : Collection<String> × String → String
```

---

## 4. Vocabulary Bindings

Vocabulary bindings map natural language patterns to typed operations. These are **strict** - each phrase has exactly one meaning.

### 4.1 Core Vocabulary

#### Collection Access
```
"the {property} of each {item} in {collection}"
  → map(collection, item => item.property)

"each {item} in {collection}"
  → iteration context, yields T from Collection<T>

"{collection} where {condition}"
  → filter(collection, condition)

"the first {item} in {collection} where {condition}"
  → find(collection, condition)

"the {item} in {collection} with the highest {property}"
  → max_by(collection, item => item.property)

"the {item} in {collection} with the lowest {property}"
  → min_by(collection, item => item.property)
```

#### Aggregation
```
"the sum of {expression} for each {item} in {collection}"
  → sum(map(collection, item => expression))

"the count of {collection}"
  → count(collection)

"the count of {collection} where {condition}"
  → count(filter(collection, condition))

"the average of {expression} for each {item} in {collection}"
  → mean(map(collection, item => expression))
```

#### Existence
```
"any {item} in {collection} has {condition}"
  → any(collection, item => condition)

"all {item} in {collection} have {condition}"
  → all(collection, item => condition)

"no {item} in {collection} has {condition}"
  → none_match(collection, item => condition)

"{collection} is empty"
  → is_empty(collection)

"{collection} is not empty"
  → not(is_empty(collection))
```

#### Binding
```
"Let {name} be {expression}"
  → immutable binding: name = expression

"Set {name} to {expression}"
  → mutable assignment: name = expression (requires Mutable<T>)

"Define {name} as {expression}"
  → reusable definition, hoisted to scope
```

#### Conditional
```
"if {condition} then {consequent} otherwise {alternative}"
  → condition ? consequent : alternative

"if {condition} then {consequent}"
  → conditional execution (statement, not expression)

"{expression} if {condition}, otherwise {default}"
  → condition ? expression : default
```

#### Comparison
```
"{a} equals {b}"                    → equals(a, b)
"{a} is {b}"                        → equals(a, b)
"{a} is not {b}"                    → not(equals(a, b))
"{a} is greater than {b}"           → greater_than(a, b)
"{a} is less than {b}"              → less_than(a, b)
"{a} is at least {b}"               → greater_than(a, b) or equals(a, b)
"{a} is at most {b}"                → less_than(a, b) or equals(a, b)
"{a} is between {b} and {c}"        → between(a, b, c)
```

#### Arithmetic
```
"{a} plus {b}"                      → add(a, b)
"{a} minus {b}"                     → subtract(a, b)
"{a} times {b}"                     → multiply(a, b)
"{a} multiplied by {b}"             → multiply(a, b)
"{a} divided by {b}"                → divide(a, b)
"{percentage} of {value}"           → multiply(percentage/100, value)
```

#### String Operations
```
"{a} followed by {b}"               → concat(a, b)
"{a} concatenated with {b}"         → concat(a, b)
"{strings} joined with {separator}" → join(strings, separator)
"{string} split by {delimiter}"     → split(string, delimiter)
"{string} trimmed"                  → trim(string)
"{string} in lowercase"             → lowercase(string)
"{string} in uppercase"             → uppercase(string)
```

#### Option/Null Handling
```
"{value} or {default} if none"
  → unwrap_or(value, default)

"if {option} exists then {expression}"
  → map on Option

"{value} exists"
  → is_some(value)

"{value} is none"
  → is_none(value)
```

#### Result/Error Handling
```
"{action}, or if that fails, {fallback}"
  → unwrap_or(action, fallback)

"{action}, or fail with {error}"
  → map_error, then propagate

"{result} succeeded"
  → is_success(result)

"{result} failed"
  → is_failure(result)

"{result} with context {message}"
  → with_context(result, message)

"fail with {error} because of {cause}"
  → failure with nested cause
```

#### Concurrency
```
"await {future}"
  → await(future)

"{action} asynchronously"
  → returns Future<T> instead of T

"spawn {task}"
  → spawn(task)  -- creates concurrent task, returns Future

"perform {tasks} in parallel"
  → all(map(tasks, spawn))  -- syntactic sugar: spawn each, await all

"the first of {futures} to complete"
  → race(futures)

"all of {futures}"
  → all(futures)

"{future} with timeout of {duration}"
  → timeout(future, duration)

"for each {item} in {stream}"
  → stream iteration

"send {value} to {channel}"
  → channel.send(value)

"receive from {channel}"
  → channel.receive()
```

### 4.2 LegiVellum Vocabulary

#### Receipt Operations
```
"accept task {definition}"
  → emit_accepted(definition)
  Creates an accepted receipt, establishing obligation

"complete task {task_id} with {outcome}"
  → emit_complete(task_id, outcome)
  Creates a complete receipt, resolving obligation

"escalate task {task_id} to {recipient} because {reason}"
  → emit_escalate(task_id, recipient, reason)
  Creates an escalate receipt, transferring responsibility

"the inbox for {principal}"
  → query_inbox(principal)
  Returns accepted receipts awaiting processing

"the timeline for {task_id}"
  → query_timeline(task_id)
  Returns all receipts in causality chain
```

#### Lease Operations
```
"claim task {task_id}"
  → acquire_lease(task_id)
  Returns Lease if successful

"renew lease {lease}"
  → renew_lease(lease)
  Extends lease duration via heartbeat

"release task {task_id}"
  → release_lease(task_id)
  Explicitly releases claim

"{lease} is expired"
  → lease.expires_at < now
```

#### Artifact Operations
```
"store artifact {content} as {mime_type}"
  → depot_store(content, mime_type)
  Returns Artifact pointer

"retrieve artifact {pointer}"
  → depot_retrieve(pointer)
  Returns artifact content
```

### 4.3 Reserved Words

These words have fixed meanings and cannot be redefined:

```
Structural:     Let, Set, Define, Given, Requires, Ensures, Can, Prohibits,
                Returns, Implementation, if, then, otherwise, for, each, in,
                where, is, as, be, to, with, of, and, or, not, match, case,
                await, async, spawn, parallel, accept, complete, escalate,
                claim, release, store, retrieve

Type keywords:  Scalar, Collection, Set, Map, Option, Result, Record, Enum,
                Mutable, Ref, Owned, Shared, Boolean, Integer, Decimal,
                String, DateTime, Duration, Future, Task, Stream, Channel,
                Receipt, Phase, Status, Principal, Lease, Artifact, ULID

LegiVellum:     accepted, complete, escalate, success, failure, canceled,
                owner, capability, trust, policy, scope, inbox, timeline

Literals:       true, false, none, empty, now (alias: the current time)
```

### 4.4 Defining Domain Vocabulary

Domain-specific terms must be explicitly defined before use:

```
Define "active user" as:
  a User where last_login is within 30 days of now
  Type: Predicate<User>

Define "pending tasks for {principal}" as:
  the inbox for principal where status is "NA"
  Type: Principal → Collection<Receipt>

Define "overdue leases" as:
  leases where expires_at is before now
  Type: Collection<Lease>
```

---

## 5. Specification Structure

### 5.1 Module Declaration

```
Module: {name}
Version: {semver}
Requires: {list of module dependencies with version constraints}
LegiVellum: {version constraint for LegiVellum compatibility}

Defines:
  {type definitions}
  {vocabulary definitions}
  {procedure definitions}
```

### 5.2 Type Definitions

```
Define record {Name}:
  {field}: {Type}
  {field}: {Type}
  ...

  Invariants:
    {constraint}
    {constraint}

Define enum {Name}:
  {Variant}
  {Variant}({Type})
  ...
```

### 5.3 Procedure Definition

```
To {name}:
  Given:
    - {param}: {Type}, {constraints}
    - {param}: {Type}

  Requires:
    - {precondition}
    - {precondition}

  Can:
    - {capability}
    - {capability}

  Prohibits:
    - {restriction}
    - {restriction}

  Returns: {Type}

  Ensures:
    - {postcondition}
    - {postcondition}

  Emits:
    - {receipt_type} on {condition}

  Implementation:
    {statements}
```

### 5.4 Capability Declarations

Capabilities are declared at the procedure level and enforced transitively. They map to LegiVellum's escalation system.

```
Capability categories:

  # Data access
  read from {resource}        Read access to data store
  write to {resource}         Write access to data store
  delete from {resource}      Delete access to data store

  # LegiVellum operations
  emit receipts               Can create receipts (requires Principal authority)
  claim tasks                 Can acquire leases from AsyncGate
  store artifacts             Can write to DepotGate
  query memory                Can read from MemoryGate

  # External services
  call {service.method}       Invoke external service (sync)
  async call {service.method} Invoke external service (async)

  # System resources
  access filesystem           Read/write filesystem
  access network              Make network requests
  access environment          Read environment variables

  # Concurrency
  spawn task                  Create concurrent tasks
  use channel                 Send/receive on channels

  # Non-determinism
  use randomness              Non-deterministic operations
  use current time            Access system clock

  # Observability
  log messages                Write to log output
  emit metrics                Record metrics
  trace operations            Record trace spans

  # Timing
  timeout after {duration}    Operation has time limit
  retry up to {n} times       Operation may retry
```

### 5.5 Capability-to-Escalation Mapping

When a procedure lacks a required capability, it must escalate:

| Missing Capability | Escalation Class |
|-------------------|------------------|
| `emit receipts` | `owner` - requires Principal authority |
| `claim tasks` | `capability` - worker cannot claim |
| `store artifacts` | `capability` - cannot write to DepotGate |
| `access network` | `capability` - network access denied |
| `access filesystem` | `capability` - filesystem access denied |
| `timeout after {d}` | `policy` - timeout exceeded |
| `retry up to {n} times` | `policy` - retry limit exceeded |
| Cross-tenant operation | `trust` - trust domain boundary |
| Task too complex | `scope` - exceeds procedure scope |

### 5.6 Contract-to-Receipt Mapping

Vellum contracts map directly to receipt lifecycle:

```
┌─────────────────────────────────────────────────────────────────┐
│                        Vellum Procedure                         │
├─────────────────────────────────────────────────────────────────┤
│  Requires:           │  Validated BEFORE accepted receipt       │
│    - preconditions   │  If violated: no receipt emitted         │
├─────────────────────────────────────────────────────────────────┤
│  Implementation:     │  Executes DURING task processing         │
│    - statements      │  Worker holds lease                      │
├─────────────────────────────────────────────────────────────────┤
│  Ensures:            │  Validated BEFORE complete receipt       │
│    - postconditions  │  If violated: escalate receipt           │
├─────────────────────────────────────────────────────────────────┤
│  Returns:            │                                          │
│    success(T)        │  → complete receipt, status: success     │
│    failure(E)        │  → escalate receipt, class from E        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Expressions and Statements

### 6.1 Expressions (produce values)

```
Literals:
  42                          Integer
  3.14                        Decimal
  "hello"                     String
  true, false                 Boolean
  none                        Option with no value
  empty                       Empty collection/set/map
  now                         Current DateTime (requires capability)
  the current time            Alias for now

Compound:
  {collection} where {predicate}
  the {aggregation} of {collection}
  {value} if {condition}, otherwise {default}
  new {Type} with {field}: {value}, ...
```

### 6.2 Statements (perform actions)

```
Binding:
  Let {name} be {expression}
  Set {name} to {expression}

Control:
  if {condition} then
    {statements}
  otherwise
    {statements}

  for each {name} in {collection}:
    {statements}

  repeat while {condition}:
    {statements}

  Return {expression}

Effects:
  Save {record} to {resource}
  Delete {record} from {resource}
  Log {level}: {message}
  {action} with {arguments}

LegiVellum:
  accept task {definition}
  complete task {task_id} with {outcome}
  escalate task {task_id} to {recipient} because {reason}

Concurrency:
  Let {future} be {action} asynchronously
  await {future}
  spawn {task}
  perform {tasks} in parallel
```

### 6.3 Pattern Matching

Pattern matching supports destructuring, guards, and exhaustiveness checking.

```
match {expression}:
  case {Pattern}:
    {statements}
  case {Pattern} if {guard}:
    {statements}
  otherwise:
    {statements}
```

### 6.4 Try/Catch Syntax (Optional Sugar)

```
Try:
  Let result be await process task
  Return success(result)
Catch CapabilityError as err:
  escalate task task_id to err.required_principal because "Missing capability"
  Return failure(err)
Catch TimeoutError as err:
  escalate task task_id to retry_handler because "Timeout exceeded"
  Return failure(err)
Catch _ as err:
  Return failure(UnknownError with err)
```

---

## 7. Effect System

### 7.1 Effect Categories

Effects are tracked in the type system and declared in capabilities.

```
Effect categories:
  Pure            No effects (can be memoized, reordered)
  IO              Reads/writes external state
  Async           May suspend and resume
  Fallible        May fail with an error
  Nondeterministic May produce different results
  Receipted       Emits LegiVellum receipts
```

### 7.2 Effect Propagation

Effects propagate through call chains. If a procedure calls another that emits receipts, the caller must also declare receipt capability.

---

## 8. Module System

### 8.1 Standard Library Modules

```
Core            Basic types and operations
Collections     Advanced collection operations
DateTime        Date and time handling
Text            String manipulation
Math            Mathematical functions
Validation      Input validation helpers
Result          Error handling utilities
Async           Future and Task utilities
Stream          Stream processing
Channel         Concurrent communication

# LegiVellum modules
LegiVellum.Receipt    Receipt types and operations
LegiVellum.Lease      Lease management
LegiVellum.Artifact   DepotGate integration
LegiVellum.Memory     MemoryGate integration
```

---

## 9. Escape Hatch: Target-Specific Implementations

When natural language is awkward or a target-specific optimization is needed, use explicit implementation blocks.

### 9.1 Target-Specific Code Blocks

```
Define "normalized email of {email}" as:
  email trimmed, in lowercase, with spaces removed
  Type: String → String

  Implementation (default):
    Let step1 be email trimmed
    Let step2 be step1 in lowercase
    Return step2 with " " replaced by ""

  Implementation (Python):
    ```
    email.strip().lower().replace(" ", "")
    ```

  Implementation (Rust):
    ```
    email.trim().to_lowercase().replace(" ", "")
    ```
```

### 9.2 Rules for Escape Hatches

1. **Default is canonical**: The natural language (default) implementation defines the authoritative semantics.

2. **Behavioral equivalence required**: All target-specific implementations MUST produce identical results to the default for all valid inputs.

3. **Type-checked**: Target implementations must match the declared type signature exactly.

4. **Tested equivalence**: Target implementations should be verified against the default.

5. **Documented rationale**: Every escape hatch must document WHY it exists.

---

## 10. File Format

### 10.1 File Extension

`.vellum`

### 10.2 File Structure

```
# {Module name}
# {Description}

Version: {semver}
LegiVellum: {version constraint}
Requires: {dependencies with version constraints}

---

{type definitions}

---

{vocabulary definitions}

---

{procedure definitions}
```

### 10.3 Example Complete File

```
# TaskProcessor
# Processes tasks from AsyncGate inbox with receipt emission

Version: 1.0.0
LegiVellum: ^1.1.0
Requires:
  - Core >= 1.0.0
  - LegiVellum.Receipt >= 1.0.0
  - LegiVellum.Lease >= 1.0.0

---

Define record TaskResult:
  task_id: ULID
  output: String
  artifacts: Collection<Artifact>
  duration: Duration

Define enum ProcessingError:
  TaskNotFound(task_id: ULID)
  LeaseExpired(task_id: ULID)
  CapabilityMissing(capability: String)
  Timeout
  InternalError(message: String)

---

Define "ready tasks for {principal}" as:
  the inbox for principal where phase is accepted
  Type: Principal → Collection<Receipt>

---

public To process next task:
  Given:
    - principal: Principal
    - worker_id: Identifier

  Requires:
    - principal is not empty
    - worker_id is not empty

  Can:
    - emit receipts
    - claim tasks
    - store artifacts
    - query memory
    - log messages
    - use current time
    - timeout after 5 minutes

  Prohibits:
    - access filesystem
    - access network

  Returns: Future<Result<TaskResult, ProcessingError>>

  Emits:
    - complete receipt on success
    - escalate receipt on failure

  Ensures:
    - if result succeeded then task has complete receipt
    - if result failed then task has escalate receipt

  Implementation:
    Let tasks be the ready tasks for principal

    if tasks is empty then
      Return failure(TaskNotFound with "No tasks available")

    Let task be the first task in tasks
    Let lease_result be claim task task.task_id

    if lease_result failed then
      Return failure(lease_result.error)

    Let lease be lease_result.value
    Let start_time be now

    Try:
      Let output be await execute task task.task_body
        with timeout of 5 minutes

      Let duration be now minus start_time

      Let result be new TaskResult with:
        - task_id: task.task_id
        - output: output
        - artifacts: empty
        - duration: duration

      complete task task.task_id with success(result)

      Return success(result)

    Catch TimeoutError as err:
      escalate task task.task_id to principal because "Timeout after 5 minutes"
      Return failure(Timeout)

    Catch _ as err:
      Log error: "Task failed: " followed by err.message
      escalate task task.task_id to principal because err.message
      Return failure(InternalError with err.message)
```

---

## 11. Design Rationale

### 11.1 Why "Vellum"?

- **Etymology**: Vellum is a writing surface for important documents
- **LegiVellum**: The legitimate/legal vellum - authoritative records
- **Vellum language**: The writing that goes ON the vellum
- **Receipts**: Written on vellum, immutable, proof of obligation

### 11.2 Why Receipt-Native?

LegiVellum solves coordination through receipts. Making receipts first-class in Vellum:

- **Explicit obligations**: Every task creates traceable receipts
- **Capability enforcement**: Missing capabilities trigger escalation
- **Provenance**: Complete causality chains through receipt linking
- **Auditability**: All state changes are receipted

### 11.3 Why Capability-to-Escalation Mapping?

Instead of runtime errors, capability violations become structured escalations:

- **No silent failures**: Missing capability = explicit escalation
- **Responsibility transfer**: Escalation moves task to capable handler
- **Policy enforcement**: Timeouts, retries become policy escalations
- **Trust boundaries**: Cross-tenant operations require trust escalation

---

## Appendix A: Grammar (Informal)

```
module      ::= header definitions
header      ::= "Module:" name "Version:" version "LegiVellum:" constraint?
                ("Requires:" dep-list)?
definitions ::= (type-def | vocab-def | proc-def | test-def)*

proc-def    ::= visibility? "To" name type-params? ":"
                given? requires? can? prohibits? returns ensures? emits?
                impl-block

emits       ::= "Emits:" emit-clause+
emit-clause ::= receipt-type "on" condition

receipt-stmt ::= "accept task" expression
               | "complete task" expression "with" expression
               | "escalate task" expression "to" expression "because" expression
```

---

## Appendix B: LegiVellum Type Reference

| Type | Description | Receipt Field |
|------|-------------|---------------|
| `ULID` | Universally unique lexicographically sortable ID | receipt_id, task_id |
| `Phase` | accepted, complete, escalate | phase |
| `Status` | NA, success, failure, canceled | status |
| `EscalationClass` | owner, capability, trust, policy, scope, other | escalation_class |
| `OutcomeKind` | NA, none, response_text, artifact_pointer, mixed | outcome_kind |
| `Principal` | Dot-notation identity | from_principal, recipient_ai |

---

## Appendix C: Capability-to-Escalation Reference

| Capability | Escalation Class | Reason |
|------------|-----------------|--------|
| `emit receipts` | owner | Requires Principal authority |
| `claim tasks` | capability | Worker cannot acquire lease |
| `store artifacts` | capability | DepotGate access denied |
| `access network` | capability | Network capability missing |
| `access filesystem` | capability | Filesystem capability missing |
| `timeout after {d}` | policy | Operation exceeded time limit |
| `retry up to {n} times` | policy | Retry attempts exhausted |
| Cross-tenant | trust | Trust domain boundary |
| Task complexity | scope | Exceeds procedure scope |

---

*End of Vellum Language Specification*
