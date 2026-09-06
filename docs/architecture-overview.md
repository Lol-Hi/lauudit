# Architecture Overview

Lauudit is a browser extension that checks the case citations in a legal-AI
answer. It runs locally on the user's computer and shows the results beside
the answer.

## The system in one view

```text
Legal-AI answer in the browser
              |
              v
     Chrome extension captures
       the visible answer
              |
              v
     Local audit service
   verifies the citations
              |
              v
 Official eLitigation check
       confirms sources
              |
              v
       Results in the side panel
```

## Main parts

### 1. Browser extension

The extension reads the answer currently visible on the page. It identifies
the most likely answer area, waits until that area has finished changing, and
captures the text, links, and citation locations.

This approach works across different websites because it looks for visible,
well-structured answer content instead of depending on one website's HTML
layout. It does not intercept the website's network traffic.

### 2. Local audit service

The extension sends the captured answer to a small service running on the same
computer. The service:

- finds case names and legal citation numbers;
- connects each citation to the relevant text in the answer; and
- creates a separate result for every citation occurrence; and
- verifies sources through the official live authority.

Keeping this work local means that the normal audit flow does not require a
cloud database or an external AI service.

### 3. Official source verification

In the default live mode, Lauudit uses Singapore's official eLitigation
service as the authority for checking whether a cited judgment can be found
and whether its basic details match.

For each citation, the service may check:

- whether the judgment exists;
- whether the case name and citation match;
- whether the answer's link points to the expected source; and
- whether the source metadata matches the cited case.

These checks are kept separate. Finding a real judgment does not, by itself,
prove that the legal claim is correct. Contextual proposition-to-holding
accuracy is not yet implemented.

### 4. Results and review

The extension's side panel presents the findings in a simple, citation-level
summary. Clear problems are flagged, while uncertain cases are marked for
human review rather than being treated as definite failures.

## What happens during an audit

1. The user selects **Audit response** in the extension.
2. The extension captures the stable, visible answer and its links.
3. The local service extracts the citations and verifies them against the
   official source.
4. The side panel displays the results and highlights the cited text.

Live verification reads the source temporarily for the current audit. The
browser page, judgment text, and source PDFs are not saved as part of that
request.

## Live verification

Formal results require **live verification** against the official eLitigation
source. The local SQLite collection is reserved for controlled implementation
and regression work, not for standalone production results.

## What changed for scalability

The current MVP scalability target is thousands of audits per day at a modest
peak rate. The recent increment makes the slowest part—the public-source
network calls—more manageable:

- requests stop waiting after three seconds;
- a circuit breaker pauses repeated transport failures for 60 seconds;
- successful live results are reused for one hour in a bounded process-local
  cache;
- citations in one audit are checked concurrently, up to eight at a time; and
- live-result handling is asynchronous and does not require a second user
  action.

This is an MVP scalability achievement, not a claim of full production
infrastructure. Shared caching, rate limiting, load testing, and distributed
queueing are future deployment work.

## Trust boundaries and current scope

Lauudit is designed to make citation checking more reliable, not to replace
legal judgment. In particular:

- a citation can be authentic while the AI's explanation is still wrong;
- unclear page captures, unknown links, and uncertain source matches are
  surfaced for review;
- contextual claim checking is not yet implemented; and
- the current MVP has bounded, cached, concurrent live verification, while
  full production infrastructure remains future work.

The completed MVP focuses on detecting fabricated, mismatched, or
unresolvable Singapore case citations and delivering those checks quickly. It
does not yet determine whether a cited passage supports the surrounding legal
claim.
