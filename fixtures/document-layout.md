# Release Readiness Report

The release decision depends on both the service metrics and the chart below.

| Service | Error rate | Decision |
|---|---:|---|
| Vision API | 0.8% | pass |
| Search API | 3.4% | investigate |

![Error rates by service. Search API exceeds the two percent review
threshold.](fixtures/document-error-rates.png)

Figure 1: Service error-rate evidence for the release review.

The Search API requires investigation because its error rate exceeds the
review threshold shown in Figure 1.
