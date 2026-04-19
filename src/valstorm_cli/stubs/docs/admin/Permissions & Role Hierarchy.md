import MermaidChart from '../../../components/MermaidChart';

# Permissions & Role Hierarchy

Your ability to view and interact with data in the system is governed by a powerful and flexible security model. This model is built on two core concepts: **Permissions** and the **Role Hierarchy**. Understanding how they work together is key to understanding what you can see and do.

  * **Permissions** control *what actions* you can perform (like viewing, creating, or editing).
  * The **Role Hierarchy** controls *which records* you have access to (like your own records, your team's records, or everyone's records).

-----

## Permissions: Controlling Your Actions

Permissions define your fundamental capabilities for each object and field in the system. They are the "verbs" of the security model—the actions you are allowed to take.

### Object & Field Level Control

Permissions operate on two levels:

1.  **Object Permissions**: These are high-level controls that grant or deny access to an entire object (e.g., 'Account', 'Contact', 'Opportunity'). The four main actions are:

      * **Create**: The ability to create new records of that object type.
      * **Read**: The ability to view records of that object type.
      * **Update**: The ability to modify existing records.
      * **Delete**: The ability to remove records.

2.  **Field Permissions**: For more granular control, administrators can set permissions on individual fields within an object. This allows them to protect sensitive information. The two field-level actions are:

      * **Read**: The ability to see the value in a specific field.
      * **Update**: The ability to change the value in a specific field.

For example, you might have `Update` permission on the 'Opportunity' object but be denied `Update` permission on the `Amount` field, making it read-only for you.

### Permission Stacking and Precedence

You can be assigned multiple sets of permissions. When permissions conflict, the system uses a simple rule: **the highest level of access wins**. If any permission set grants you access to an action, you will have that access, even if another permission set denies it.

This "stacking" allows for flexible security. A base permission set can be applied to all users, with more privileged sets layered on top for specific groups.

<MermaidChart chart={`
graph TD
    subgraph "Permission Sets"
        A[Sales Rep Permissions <br> - Update Opportunity: True <br> - Update Amount Field: False]
        B[Sales Manager Add-on <br> - Update Amount Field: True]
    end

    subgraph "User Assignment"
        C(User is assigned BOTH sets)
    end

    subgraph "Final Access"
        D{Effective Permissions <br> - Update Opportunity: True <br> - Update Amount Field: True}
    end

    A --> C
    B --> C
    C --> D

    style D fill:#d4edda,stroke:#c3e6cb
`} />

*In the diagram above, the user gains the ability to update the 'Amount' field because the "Sales Manager Add-on" permission overrides the restriction from the base "Sales Rep" set.*

-----

## Role Hierarchy: Controlling Data Visibility

While permissions define *what you can do*, roles define *which records you can see*. The role hierarchy is typically modeled after your organization's structure, creating a parent-child relationship between roles (e.g., a Sales Manager is the parent role to several Sales Rep roles).

This structure enables data to "roll up," meaning users higher in the hierarchy gain visibility into the records of users below them. Data access is determined by the **View Access** level set on your role.

<MermaidChart chart={`
graph TD
    CEO(CEO <br> Full Access)
    VP_Sales(VP of Sales <br> Subordinate Access)
    Sales_Mgr1(Sales Mgr A <br> Subordinate Access)
    Sales_Mgr2(Sales Mgr B <br> Subordinate Access)
    Rep1(Sales Rep 1 <br> Team Access)
    Rep2(Sales Rep 2 <br> Team Access)
    Rep3(Sales Rep 3 <br> Personal Access)
    Rep4(Sales Rep 4 <br> Team Access)

    VP_Sales --> CEO
    Sales_Mgr1 --> VP_Sales
    Sales_Mgr2 --> VP_Sales
    Rep1 --> Sales_Mgr1
    Rep2 --> Sales_Mgr1
    Rep3 --> Sales_Mgr2
    Rep4 --> Sales_Mgr2

    style CEO fill:#cce5ff,stroke:#b8daff
`} />

### Data Access Levels

Your role will have one of the following access levels, which determines the records you can see based on record ownership.

  * **Personal**: You can only view and edit records that you personally own. You cannot see records owned by your colleagues, even those with the same role.

      * *Example*: `Rep 3` can only see their own records.

  * **Team**: You can view and edit records owned by you AND any other user who shares the same role.

      * *Example*: `Rep 1` and `Rep 2` can see each other's records because they share the "Sales Mgr A" team.

  * **Subordinate**: You can view and edit records owned by you, your team, AND anyone in roles beneath you in the hierarchy. This is the standard for managers.

      * *Example*: `Sales Mgr A` can see records owned by `Rep 1` and `Rep 2`. The `VP of Sales` can see records owned by both `Sales Mgr A` and `Sales Mgr B` and all their subordinate reps.

  * **Full**: You can see all records for an object, regardless of who owns them. This is typically reserved for administrators or executive roles.

      * *Example*: The `CEO` can see every record in the system.

-----

## Record-Level Sharing: Granular Exceptions

Sometimes, you need to collaborate on a specific record with someone who wouldn't normally have access to it based on the Role Hierarchy. This is where **Record-Level Sharing** comes in.

Record-Level Sharing allows you to explicitly grant access to a single record to individual users, completely bypassing the standard Role Hierarchy. 

### How Sharing Works

When you share a record with another user, you assign them a specific **Access Level** for that record:

*   **Read**: The user can view the record but cannot make any changes.
*   **Edit**: The user can view and modify the record's data.
*   **Delete**: The user has full control, including the ability to permanently delete the record.

**Important Rules of Sharing:**
*   **Ownership Precedence**: The owner of a record (and administrators) always maintains full control.
*   **Hierarchy Bypass**: Sharing a record grants access *across* or *up* the hierarchy. For example, a Sales Rep (`Personal` access) can share a specific Deal record with another Sales Rep on a different team, allowing them to collaborate on that one deal without exposing their entire pipeline.
*   **Strict Enforcement**: Sharing permissions are strictly enforced. If a user is granted `Read` access via sharing, the system will actively block them from saving edits or deleting the record, even if their broader Object Permissions technically allow those actions. The sharing access level acts as a ceiling for that specific record.

-----

### Putting It All Together

Your final access is a combination of your **Permissions**, your **Role**, and any **Record-Level Sharing**.

Imagine you are `Sales Mgr A`.

1.  Your **Role** grants you `Subordinate` access, so you can **see** all Opportunity records owned by `Rep 1` and `Rep 2`.
2.  Your **Permissions** grant you `Update` access on the Opportunity object but deny you `Delete` access.

The result is that you can view and edit your team's Opportunities, but you cannot delete them. This powerful combination allows for precise and secure control over your organization's data.
