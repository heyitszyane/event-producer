@orchestrator
Feature: Orchestrator Agent
  The Orchestrator is the top-level agent that routes user messages to the
  correct specialist agent (Brief/Scope, Budget Manager, Production Manager,
  Vendor Coordinator, Risk Flagger). It enforces the action-gate on every
  financial or state-changing request and returns structured JSON responses.

  Scenario: Routes user message to Budget Manager
    Given a user message "What's our budget status for the networking event?"
    And the Orchestrator has access to the Budget Manager agent
    When the Orchestrator processes the message
    Then the message is routed to the Budget Manager agent
    And the response contains a "budget_summary" field
    And the response is valid JSON

  Scenario: Routes user message to Production Manager
    Given a user message "Show me the run-of-show timeline"
    And the Orchestrator has access to the Production Manager agent
    When the Orchestrator processes the message
    Then the message is routed to the Production Manager agent
    And the response contains a "schedule" or "call_sheet" field
    And the response is valid JSON

  Scenario: Routes user message to Vendor Coordinator
    Given a user message "Draft an RFP for the catering vendor"
    And the Orchestrator has access to the Vendor Coordinator agent
    When the Orchestrator processes the message
    Then the message is routed to the Vendor Coordinator agent
    And the response contains a "vendor_brief" or "rfp" field
    And the response is valid JSON

  Scenario: Returns status for unrecognized input
    Given a user message "What's the weather like today?"
    And no specialist agent matches the message intent
    When the Orchestrator processes the message
    Then the response contains a "status" field set to "unrecognized"
    And the response contains a "message" field explaining no agent matched
    And the response is valid JSON

  Scenario: Enforces action-gate on financial actions
    Given a user message "Send the payment to vendor ABC for $5000"
    And the action "send_vendor_message" requires approval per the action-gate
    And no Approval object is provided
    When the Orchestrator processes the message
    Then the response contains a "status" field set to "approval_required"
    And the response contains an "action" field identifying the gated action
    And no outbound vendor message is sent
    And the response is valid JSON

  Scenario: Enforces action-gate blocks unapproved scope change
    Given a user message "Change the event scope to add a photo booth"
    And the action "change_scope" requires approval per the action-gate
    And an Approval object is provided with status "pending"
    When the Orchestrator processes the message
    Then the response contains a "status" field set to "approval_required"
    And the response indicates the Approval status is "pending"
    And no scope change is executed
    And the response is valid JSON

  Scenario: Allows non-gated informational actions without approval
    Given a user message "List all vendors for the event"
    And the action "list_vendors" is not in the gated actions set
    When the Orchestrator processes the message
    Then the response contains a "status" field set to "ok"
    And the response contains vendor data
    And no Approval object is required

  Scenario: Returns structured JSON response
    Given any valid user message
    When the Orchestrator processes the message
    Then the response is valid JSON
    And the response contains a "status" field
    And the response contains an "agent" field identifying which agent handled the request
