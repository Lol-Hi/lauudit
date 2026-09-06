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
   finds and separates citations
              |
              v
 Official eLitigation verification
       checks each citation
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
- creates a separate result for every citation occurrence.

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
- whether the cited judgment appears to support the nearby legal claim.

These checks are kept separate. Finding a real judgment does not, by itself,
prove that the legal claim is correct.

### 4. Results and review

The extension's side panel presents the findings in a simple, citation-level
summary. Clear problems are flagged, while uncertain cases are marked for
human review rather than being treated as definite failures.

## What happens during an audit

1. The user selects **Audit response** in the extension.
2. The extension captures the stable, visible answer and its links.
3. The local service extracts the citations and the claims around them.
4. The service verifies each citation against the official source.
5. The side panel displays the results and explains which checks passed,
   failed, or need review.

Live verification reads the source temporarily for the current audit. The
browser page, judgment text, and source PDFs are not saved as part of that
request.

## Live mode and offline mode

Lauudit has two ways to work:

- **Live mode (default):** checks citations against the official eLitigation
  source. This is the mode used for the main authenticity demonstration.
- **Offline mode:** checks against an optional local SQLite collection. This
  is useful for development and repeatable tests, but a missing case in the
  local collection does not prove that the case does not exist.

## Trust boundaries and current scope

Lauudit is designed to make citation checking more reliable, not to replace
legal judgment. In particular:

- a citation can be authentic while the AI's explanation is still wrong;
- unclear page captures, unknown links, and uncertain source matches are
  surfaced for review;
- contextual claim checking is an optional evidence-based step; and
- the current request path is synchronous and has not yet been prepared for
  production-scale traffic with queues, caching, rate limits, and monitoring.

The completed MVP focuses on detecting fabricated, mismatched, or
unresolvable Singapore case citations. It also includes an optional path for
checking whether a cited passage supports the surrounding claim.
