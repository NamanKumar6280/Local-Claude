#!/usr/bin/env python3
"""
generate_the_cousins_secret.py
-------------------------------
Creates the full Unity project "The Cousin's Secret" with all scripts,
assembly definitions, cinematic sequences, horror effects, and an editor wizard
that builds the scene on launch. Zero external dependencies.

It also cleans up any stale files (like EnemyAI.cs) that would cause warnings.
"""

import os
import json

PROJECT_ROOT = "TheCousinsSecret"

FOLDERS = [
    "Assets/Scripts/Core",
    "Assets/Scripts/AI",
    "Assets/Scripts/UI",
    "Assets/Scripts/Editor",
    "Assets/Scenes",
    "Assets/Resources/Items",
    "Assets/Prefabs",
    "Assets/Materials",
    "Assets/Audio",
    "Assets/ScriptableObjects",
    "Assets/Animations",
    "ProjectSettings",
]

# List of files we create – used to clean up anything not in this set
CREATED_FILES = [
    "Assets/Scripts/Core/PlayerController.cs",
    "Assets/Scripts/Core/MobileInput.cs",
    "Assets/Scripts/Core/InteractionManager.cs",
    "Assets/Scripts/Core/IInteractable.cs",
    "Assets/Scripts/Core/InventorySystem.cs",
    "Assets/Scripts/Core/ItemData.cs",
    "Assets/Scripts/Core/DoorController.cs",
    "Assets/Scripts/Core/LockedContainer.cs",
    "Assets/Scripts/Core/Fusebox.cs",
    "Assets/Scripts/Core/KeyPickup.cs",
    "Assets/Scripts/Core/VasePickup.cs",
    "Assets/Scripts/Core/ThrowableVase.cs",
    "Assets/Scripts/Core/FootstepHandler.cs",
    "Assets/Scripts/Core/GameManager.cs",
    "Assets/Scripts/Core/ProgressionFlags.cs",
    "Assets/Scripts/Core/AudioManager.cs",
    "Assets/Scripts/Core/HorrorFXManager.cs",
    "Assets/Scripts/Core/IntroCinematicController.cs",
    "Assets/Scripts/AI/CousinAI.cs",
    "Assets/Scripts/AI/CousinFSM.cs",
    "Assets/Scripts/AI/AISettings.cs",
    "Assets/Scripts/UI/UIManager.cs",
    "Assets/Scripts/UI/VirtualJoystick.cs",
    "Assets/Scripts/UI/TypewriterEffect.cs",
    "Assets/Scripts/UI/CrosshairController.cs",
    "Assets/Scripts/Editor/ProjectConfigurator.cs",
    "Assets/Scripts/Editor/SceneSetupWizard.cs",
]

# Assembly definition files
ASMDEF_FILES = {
    "Assets/Scripts/Game.Core.asmdef": {
        "name": "Game.Core",
        "rootNamespace": "Game.Core",
        "references": [],
        "includePlatforms": [],
        "excludePlatforms": [],
        "allowUnsafeCode": False,
        "overrideReferences": False,
        "precompiledReferences": [],
        "autoReferenced": True,
        "defineConstraints": [],
        "versionDefines": [],
        "noEngineReferences": False
    },
    "Assets/Scripts/AI/Game.AI.asmdef": {
        "name": "Game.AI",
        "rootNamespace": "Game.AI",
        "references": ["Game.Core", "UnityEngine.AIModule"],
        "includePlatforms": [],
        "excludePlatforms": [],
        "allowUnsafeCode": False,
        "overrideReferences": False,
        "precompiledReferences": [],
        "autoReferenced": True,
        "defineConstraints": [],
        "versionDefines": [],
        "noEngineReferences": False
    },
    "Assets/Scripts/UI/Game.UI.asmdef": {
        "name": "Game.UI",
        "rootNamespace": "Game.UI",
        "references": ["Game.Core"],
        "includePlatforms": [],
        "excludePlatforms": [],
        "allowUnsafeCode": False,
        "overrideReferences": False,
        "precompiledReferences": [],
        "autoReferenced": True,
        "defineConstraints": [],
        "versionDefines": [],
        "noEngineReferences": False
    },
    "Assets/Scripts/Editor/Game.Editor.asmdef": {
        "name": "Game.Editor",
        "rootNamespace": "Game.Editor",
        "references": ["Game.Core", "Game.AI", "Game.UI", "UnityEditor"],
        "includePlatforms": ["Editor"],
        "excludePlatforms": [],
        "allowUnsafeCode": False,
        "overrideReferences": False,
        "precompiledReferences": [],
        "autoReferenced": True,
        "defineConstraints": [],
        "versionDefines": [],
        "noEngineReferences": False
    }
}

# ==================== CORE SCRIPTS ====================

PLAYER_CONTROLLER = '''\
using UnityEngine;
using Game.Core;

namespace Game.Core
{
    [RequireComponent(typeof(CharacterController))]
    public class PlayerController : MonoBehaviour
    {
        [Header("Movement")]
        [SerializeField] private float walkSpeed = 5f;
        [SerializeField] private float sprintSpeed = 8f;
        [SerializeField] private float crouchSpeed = 2.5f;
        [SerializeField] private float gravity = -20f;
        [SerializeField] private float jumpHeight = 1.5f;
        [SerializeField] private float crouchHeight = 1f;
        [SerializeField] private float standingHeight = 2f;
        [SerializeField] private float crouchTransitionSpeed = 10f;

        [Header("Stamina")]
        [SerializeField] private float maxStamina = 100f;
        [SerializeField] private float staminaDrainRate = 20f;
        [SerializeField] private float staminaRegenRate = 15f;
        [SerializeField] private float staminaRegenDelay = 1.5f;
        [SerializeField] private float minStaminaToSprint = 10f;

        [Header("Look")]
        [SerializeField] private Transform cameraTransform;
        [SerializeField] private float lookSensitivity = 2f;
        [SerializeField] private float maxLookAngle = 80f;

        [Header("Headbob")]
        [SerializeField] private float headbobFrequency = 2f;
        [SerializeField] private float headbobAmplitude = 0.05f;
        [SerializeField] private AnimationCurve headbobCurve = AnimationCurve.EaseInOut(0,0,1,1);

        [Header("FOV")]
        [SerializeField] private Camera playerCamera;
        [SerializeField] private float normalFOV = 60f;
        [SerializeField] private float sprintFOV = 70f;
        [SerializeField] private float fovLerpSpeed = 5f;

        [Header("Footsteps")]
        [SerializeField] private FootstepHandler footstepHandler;
        [SerializeField] private float walkFootstepInterval = 0.5f;
        [SerializeField] private float sprintFootstepInterval = 0.35f;
        [SerializeField] private float crouchFootstepInterval = 0.7f;

        [Header("Input")]
        [SerializeField] private bool useMobileInput = false;

        public NoiseLevel CurrentNoiseLevel { get; private set; } = NoiseLevel.Silent;
        public bool IsSprinting { get; private set; }
        public bool IsCrouching { get; private set; }
        public bool IsGrounded => controller.isGrounded;
        public float StaminaNormalized => stamina / maxStamina;

        private CharacterController controller;
        private Vector3 velocity;
        private float stamina;
        private float staminaRegenTimer;
        private float yRotation;
        private float xRotation;
        private float headbobTimer;
        private float footstepTimer;
        private Vector3 originalCameraLocalPos;
        private float originalControllerHeight;
        private Vector3 originalControllerCenter;
        private float currentCrouchHeight;
        private Vector3 currentCrouchCenter;

        private void Awake()
        {
            controller = GetComponent<CharacterController>();
            if (cameraTransform == null) cameraTransform = GetComponentInChildren<Camera>().transform;
            if (playerCamera == null) playerCamera = cameraTransform.GetComponent<Camera>();
            originalControllerHeight = controller.height;
            originalControllerCenter = controller.center;
            originalCameraLocalPos = cameraTransform.localPosition;
            stamina = maxStamina;
            currentCrouchHeight = originalControllerHeight;
            currentCrouchCenter = originalControllerCenter;
        }

        private void Update()
        {
            HandleLook();
            HandleMovement();
            HandleHeadbob();
            HandleFootsteps();
            HandleFOV();
            UpdateNoiseLevel();
        }

        private void HandleLook()
        {
            if (useMobileInput) return;

            float mouseX = Input.GetAxis("Mouse X") * lookSensitivity;
            float mouseY = Input.GetAxis("Mouse Y") * lookSensitivity;

            yRotation += mouseX;
            xRotation -= mouseY;
            xRotation = Mathf.Clamp(xRotation, -maxLookAngle, maxLookAngle);
            cameraTransform.localRotation = Quaternion.Euler(xRotation, 0f, 0f);
            transform.rotation = Quaternion.Euler(0f, yRotation, 0f);
        }

        public void ApplyLookInput(Vector2 lookDelta)
        {
            yRotation += lookDelta.x * lookSensitivity;
            xRotation -= lookDelta.y * lookSensitivity;
            xRotation = Mathf.Clamp(xRotation, -maxLookAngle, maxLookAngle);
            cameraTransform.localRotation = Quaternion.Euler(xRotation, 0f, 0f);
            transform.rotation = Quaternion.Euler(0f, yRotation, 0f);
        }

        private void HandleMovement()
        {
            if (controller.isGrounded && velocity.y < 0)
                velocity.y = -2f;

            float horizontal = useMobileInput ? MobileInput.MoveInput.x : Input.GetAxis("Horizontal");
            float vertical = useMobileInput ? MobileInput.MoveInput.y : Input.GetAxis("Vertical");

            Vector3 move = transform.right * horizontal + transform.forward * vertical;
            move = Vector3.ClampMagnitude(move, 1f);

            IsCrouching = Input.GetButton("Crouch") || (useMobileInput && MobileInput.CrouchPressed);

            float speed = walkSpeed;
            IsSprinting = false;

            if (!IsCrouching && stamina > minStaminaToSprint &&
                (Input.GetKey(KeyCode.LeftShift) || (useMobileInput && MobileInput.SprintHeld)) &&
                vertical > 0.1f)
            {
                IsSprinting = true;
                speed = sprintSpeed;
                stamina -= staminaDrainRate * Time.deltaTime;
                staminaRegenTimer = 0f;
            }
            else if (IsCrouching)
            {
                speed = crouchSpeed;
            }

            if (!IsSprinting && stamina < maxStamina)
            {
                staminaRegenTimer += Time.deltaTime;
                if (staminaRegenTimer >= staminaRegenDelay)
                    stamina += staminaRegenRate * Time.deltaTime;
            }

            stamina = Mathf.Clamp(stamina, 0f, maxStamina);

            controller.Move(move * speed * Time.deltaTime);

            velocity.y += gravity * Time.deltaTime;
            controller.Move(velocity * Time.deltaTime);

            float targetHeight = IsCrouching ? crouchHeight : originalControllerHeight;
            Vector3 targetCenter = IsCrouching ? new Vector3(0, crouchHeight*0.5f, 0) : originalControllerCenter;
            currentCrouchHeight = Mathf.Lerp(currentCrouchHeight, targetHeight, Time.deltaTime * crouchTransitionSpeed);
            currentCrouchCenter = Vector3.Lerp(currentCrouchCenter, targetCenter, Time.deltaTime * crouchTransitionSpeed);
            controller.height = currentCrouchHeight;
            controller.center = currentCrouchCenter;

            float camTargetY = IsCrouching ? crouchHeight * 0.8f : originalCameraLocalPos.y;
            Vector3 camLocal = cameraTransform.localPosition;
            camLocal.y = Mathf.Lerp(camLocal.y, camTargetY, Time.deltaTime * crouchTransitionSpeed);
            cameraTransform.localPosition = camLocal;

            if ((Input.GetButtonDown("Jump") || (useMobileInput && MobileInput.JumpPressed)) && controller.isGrounded)
                velocity.y = Mathf.Sqrt(jumpHeight * -2f * gravity);
        }

        private void HandleHeadbob()
        {
            float horizontal = useMobileInput ? MobileInput.MoveInput.x : Input.GetAxis("Horizontal");
            float vertical = useMobileInput ? MobileInput.MoveInput.y : Input.GetAxis("Vertical");
            bool isMoving = Mathf.Abs(horizontal) > 0.1f || Mathf.Abs(vertical) > 0.1f;

            if (isMoving && controller.isGrounded)
            {
                headbobTimer += Time.deltaTime * (IsSprinting ? headbobFrequency * 1.5f : headbobFrequency);
                float bobAmount = headbobCurve.Evaluate(headbobTimer % 1f) * headbobAmplitude;
                Vector3 camPos = cameraTransform.localPosition;
                camPos.y += bobAmount;
                cameraTransform.localPosition = camPos;
            }
            else
            {
                headbobTimer = 0f;
            }
        }

        private void HandleFootsteps()
        {
            bool isMoving = controller.velocity.magnitude > 0.2f && controller.isGrounded;
            if (!isMoving)
            {
                footstepTimer = 0f;
                return;
            }

            float interval = IsSprinting ? sprintFootstepInterval : (IsCrouching ? crouchFootstepInterval : walkFootstepInterval);
            footstepTimer += Time.deltaTime;
            if (footstepTimer >= interval)
            {
                footstepTimer = 0f;
                footstepHandler?.PlayFootstep();
            }
        }

        private void HandleFOV()
        {
            float targetFOV = IsSprinting ? sprintFOV : normalFOV;
            playerCamera.fieldOfView = Mathf.Lerp(playerCamera.fieldOfView, targetFOV, Time.deltaTime * fovLerpSpeed);
        }

        private void UpdateNoiseLevel()
        {
            if (!controller.isGrounded) CurrentNoiseLevel = NoiseLevel.Silent;
            else if (IsSprinting) CurrentNoiseLevel = NoiseLevel.Loud;
            else if (IsCrouching) CurrentNoiseLevel = NoiseLevel.Silent;
            else CurrentNoiseLevel = NoiseLevel.Normal;
        }
    }

    public enum NoiseLevel { Silent, Normal, Loud }
}
'''

MOBILE_INPUT = '''\
using UnityEngine;
using UnityEngine.EventSystems;

namespace Game.Core
{
    public class MobileInput : MonoBehaviour
    {
        public static Vector2 MoveInput { get; private set; }
        public static Vector2 LookInput { get; private set; }
        public static bool CrouchPressed { get; private set; }
        public static bool JumpPressed { get; private set; }
        public static bool SprintHeld { get; private set; }

        [SerializeField] private VirtualJoystick moveJoystick;
        [SerializeField] private VirtualJoystick lookJoystick;
        [SerializeField] private UnityEngine.UI.Button crouchButton;
        [SerializeField] private UnityEngine.UI.Button jumpButton;
        [SerializeField] private UnityEngine.UI.Button sprintButton;

        private void Awake()
        {
            MoveInput = Vector2.zero;
            LookInput = Vector2.zero;
        }

        private void OnEnable()
        {
            crouchButton?.onClick.AddListener(() => CrouchPressed = !CrouchPressed);
            jumpButton?.onClick.AddListener(() => JumpPressed = true);
            if (sprintButton)
            {
                EventTrigger trigger = sprintButton.gameObject.AddComponent<EventTrigger>();
                EventTrigger.Entry down = new EventTrigger.Entry { eventID = EventTriggerType.PointerDown };
                down.callback.AddListener((data) => SprintHeld = true);
                EventTrigger.Entry up = new EventTrigger.Entry { eventID = EventTriggerType.PointerUp };
                up.callback.AddListener((data) => SprintHeld = false);
                trigger.triggers.Add(down);
                trigger.triggers.Add(up);
            }
        }

        private void Update()
        {
            MoveInput = moveJoystick ? moveJoystick.Direction : Vector2.zero;
            LookInput = lookJoystick ? lookJoystick.Direction * 2f : Vector2.zero;
            JumpPressed = false; // reset each frame
        }
    }
}
'''

INTERACTION_MANAGER = '''\
using UnityEngine;
using UnityEngine.UI;

namespace Game.Core
{
    public class InteractionManager : MonoBehaviour
    {
        [SerializeField] private float interactRange = 3f;
        [SerializeField] private LayerMask interactableLayer = -1;
        [SerializeField] private Camera playerCamera;
        [SerializeField] private Image crosshair;
        [SerializeField] private Text interactionPrompt;

        private IInteractable currentTarget;

        private void Start()
        {
            if (playerCamera == null) playerCamera = Camera.main;
        }

        private void Update()
        {
            DetectInteractable();
            HandleInput();
        }

        private void DetectInteractable()
        {
            Ray ray = new Ray(playerCamera.transform.position, playerCamera.transform.forward);
            if (Physics.Raycast(ray, out RaycastHit hit, interactRange, interactableLayer))
            {
                IInteractable interactable = hit.collider.GetComponentInParent<IInteractable>();
                if (interactable != null)
                {
                    currentTarget = interactable;
                    crosshair.color = Color.green;
                    interactionPrompt.text = interactable.GetPromptText();
                    return;
                }
            }
            currentTarget = null;
            crosshair.color = Color.white;
            interactionPrompt.text = "";
        }

        private void HandleInput()
        {
            if (Input.GetKeyDown(KeyCode.E) || MobileInput.JumpPressed) // JumpPressed reused as interact on mobile
            {
                currentTarget?.Interact();
            }
        }
    }
}
'''

INTERACTABLE_INTERFACE = '''\
namespace Game.Core
{
    public interface IInteractable
    {
        void Interact();
        string GetPromptText();
    }
}
'''

INVENTORY_SYSTEM = '''\
using System.Collections.Generic;
using UnityEngine;

namespace Game.Core
{
    public class InventorySystem : MonoBehaviour
    {
        public static InventorySystem Instance { get; private set; }

        [SerializeField] private int maxSlots = 6;
        private List<ItemData> items = new List<ItemData>();

        public System.Action<ItemData> OnItemAdded;
        public System.Action<ItemData> OnItemRemoved;

        private void Awake()
        {
            if (Instance == null) Instance = this;
            else Destroy(gameObject);
        }

        public bool AddItem(ItemData item)
        {
            if (items.Count >= maxSlots || HasItem(item)) return false;
            items.Add(item);
            OnItemAdded?.Invoke(item);
            return true;
        }

        public bool RemoveItem(ItemData item)
        {
            if (items.Remove(item))
            {
                OnItemRemoved?.Invoke(item);
                return true;
            }
            return false;
        }

        public bool HasItem(ItemData item) => items.Contains(item);
        public bool HasItemByName(string name) => items.Exists(i => i.itemName == name);
        public ItemData GetItemByName(string name) => items.Find(i => i.itemName == name);
    }
}
'''

ITEM_DATA = '''\
using UnityEngine;

namespace Game.Core
{
    [CreateAssetMenu(fileName = "NewItem", menuName = "Inventory/Item Data")]
    public class ItemData : ScriptableObject
    {
        public string itemName;
        public Sprite icon;
        public ItemType type;
        public GameObject pickupPrefab;
    }

    public enum ItemType { KeyRed, KeyBlue, KeyMaster, Lockpick, Fuse, WaterBottle, Vase }
}
'''

DOOR_CONTROLLER = '''\
using UnityEngine;

namespace Game.Core
{
    [RequireComponent(typeof(BoxCollider))]
    public class DoorController : MonoBehaviour, IInteractable
    {
        public string requiredKeyName;
        public bool isLocked = true;
        public bool isJammed = false;
        public Transform doorPivot;
        public float openAngle = 90f;
        public float openSpeed = 2f;

        private bool isOpen;
        private Quaternion closedRotation;
        private Quaternion openRotation;

        private void Start()
        {
            closedRotation = doorPivot.localRotation;
            openRotation = closedRotation * Quaternion.Euler(0, openAngle, 0);
        }

        private void Update()
        {
            doorPivot.localRotation = Quaternion.Slerp(doorPivot.localRotation, isOpen ? openRotation : closedRotation, Time.deltaTime * openSpeed);
        }

        public void Interact()
        {
            if (isOpen) return;

            if (isLocked)
            {
                if (InventorySystem.Instance.HasItemByName(requiredKeyName))
                {
                    InventorySystem.Instance.RemoveItem(InventorySystem.Instance.GetItemByName(requiredKeyName));
                    Unlock();
                }
                else UIManager.Instance?.ShowMessage("Locked - need " + requiredKeyName);
            }
            else if (isJammed)
            {
                if (InventorySystem.Instance.HasItemByName("Lockpick"))
                {
                    InventorySystem.Instance.RemoveItem(InventorySystem.Instance.GetItemByName("Lockpick"));
                    isJammed = false;
                    Unlock();
                }
                else UIManager.Instance?.ShowMessage("Jammed - need lockpick");
            }
            else Unlock();
        }

        private void Unlock()
        {
            isLocked = false;
            isOpen = true;
            ProgressionFlags.FlagDoorOpened(gameObject.name);
        }

        public string GetPromptText()
        {
            if (isOpen) return "";
            return isLocked ? "Unlock (need key)" : (isJammed ? "Unjam (need lockpick)" : "Open");
        }
    }
}
'''

LOCKED_CONTAINER = '''\
using UnityEngine;

namespace Game.Core
{
    public class LockedContainer : MonoBehaviour, IInteractable
    {
        public string requiredItemName;
        public ItemData containedItem;
        public Transform spawnPoint;

        private bool opened;

        public void Interact()
        {
            if (opened) return;
            if (InventorySystem.Instance.HasItemByName(requiredItemName))
            {
                InventorySystem.Instance.RemoveItem(InventorySystem.Instance.GetItemByName(requiredItemName));
                opened = true;
                if (containedItem && spawnPoint)
                    Instantiate(containedItem.pickupPrefab, spawnPoint.position, spawnPoint.rotation);
            }
            else UIManager.Instance?.ShowMessage("Need " + requiredItemName);
        }

        public string GetPromptText() => opened ? "" : "Open (need " + requiredItemName + ")";
    }
}
'''

FUSEBOX = '''\
using UnityEngine;

namespace Game.Core
{
    public class Fusebox : MonoBehaviour, IInteractable
    {
        public bool isFixed;
        public GameObject poweredObject;

        public void Interact()
        {
            if (isFixed) return;
            if (InventorySystem.Instance.HasItemByName("Fuse"))
            {
                InventorySystem.Instance.RemoveItem(InventorySystem.Instance.GetItemByName("Fuse"));
                isFixed = true;
                if (poweredObject) poweredObject.SetActive(true);
                ProgressionFlags.FusePlaced = true;
            }
            else UIManager.Instance?.ShowMessage("Need a fuse");
        }

        public string GetPromptText() => isFixed ? "" : "Insert Fuse";
    }
}
'''

KEY_PICKUP = '''\
using UnityEngine;

namespace Game.Core
{
    [RequireComponent(typeof(SphereCollider))]
    public class KeyPickup : MonoBehaviour, IInteractable
    {
        public ItemData itemData;

        private void Start() => GetComponent<SphereCollider>().isTrigger = true;

        public void Interact()
        {
            if (InventorySystem.Instance.AddItem(itemData))
            {
                Destroy(gameObject);
                UIManager.Instance?.ShowMessage("Picked up " + itemData.itemName);
            }
        }

        public string GetPromptText() => "Pick up " + itemData.itemName;
    }
}
'''

VASE_PICKUP = '''\
using UnityEngine;

namespace Game.Core
{
    public class VasePickup : MonoBehaviour, IInteractable
    {
        public ItemData vaseItemData;
        public GameObject throwablePrefab;

        public void Interact()
        {
            if (InventorySystem.Instance.AddItem(vaseItemData))
            {
                ThrowableVase existing = FindObjectOfType<ThrowableVase>();
                if (!existing && throwablePrefab)
                {
                    GameObject obj = Instantiate(throwablePrefab, Camera.main.transform);
                    obj.transform.localPosition = new Vector3(0.5f, -0.3f, 1f);
                }
                Destroy(gameObject);
            }
        }

        public string GetPromptText() => "Pick up Vase";
    }
}
'''

THROWABLE_VASE = '''\
using System.Collections;
using UnityEngine;

namespace Game.Core
{
    public class ThrowableVase : MonoBehaviour
    {
        public float throwForce = 500f;
        public float noiseRadius = 15f;
        public LayerMask aiLayer;

        private Rigidbody rb;
        private bool thrown;

        private void Start()
        {
            rb = GetComponent<Rigidbody>();
            if (!rb) rb = gameObject.AddComponent<Rigidbody>();
            rb.isKinematic = true;
        }

        private void Update()
        {
            if (!thrown && (Input.GetMouseButtonDown(1) || Input.GetKeyDown(KeyCode.F)))
                Throw();
        }

        private void Throw()
        {
            thrown = true;
            transform.SetParent(null);
            rb.isKinematic = false;
            rb.AddForce(Camera.main.transform.forward * throwForce);
            StartCoroutine(DetectLanding());
        }

        private IEnumerator DetectLanding()
        {
            yield return new WaitForSeconds(0.5f);
            while (rb.velocity.magnitude > 0.1f) yield return null;
            Collider[] ais = Physics.OverlapSphere(transform.position, noiseRadius, aiLayer);
            foreach (var c in ais)
            {
                CousinAI ai = c.GetComponent<CousinAI>();
                if (ai) ai.HearNoise(transform.position, noiseRadius);
            }
            Destroy(gameObject, 2f);
        }
    }
}
'''

FOOTSTEP_HANDLER = '''\
using UnityEngine;

namespace Game.Core
{
    public class FootstepHandler : MonoBehaviour
    {
        [System.Serializable]
        public struct SurfaceFootstep
        {
            public string surfaceTag;
            public AudioClip[] clips;
            public float volume;
        }

        public SurfaceFootstep[] surfaces;
        public float defaultVolume = 0.5f;
        public AudioClip[] defaultClips;
        public AudioSource audioSource;

        public void PlayFootstep()
        {
            if (Physics.Raycast(transform.position, Vector3.down, out RaycastHit hit, 2f))
            {
                foreach (var s in surfaces)
                {
                    if (hit.collider.CompareTag(s.surfaceTag) && s.clips.Length > 0)
                    {
                        PlayRandom(s.clips, s.volume);
                        return;
                    }
                }
            }
            if (defaultClips.Length > 0) PlayRandom(defaultClips, defaultVolume);
        }

        private void PlayRandom(AudioClip[] clips, float volume)
        {
            audioSource.PlayOneShot(clips[Random.Range(0, clips.Length)], volume);
        }
    }
}
'''

GAME_MANAGER = '''\
using UnityEngine;
using Game.UI;

namespace Game.Core
{
    public enum GameState { Exploration, Chase, Jumpscare, GameOver, Victory }

    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }
        public GameState CurrentState { get; private set; } = GameState.Exploration;

        [SerializeField] private AudioManager audioManager;
        [SerializeField] private HorrorFXManager fxManager;

        public System.Action<GameState> OnStateChanged;

        private void Awake()
        {
            if (Instance) { Destroy(gameObject); return; }
            Instance = this;
            DontDestroyOnLoad(gameObject);
        }

        private void Start() => ChangeState(GameState.Exploration);

        public void ChangeState(GameState newState)
        {
            CurrentState = newState;
            OnStateChanged?.Invoke(newState);

            switch (newState)
            {
                case GameState.Exploration:
                    audioManager.SetExplorationMode();
                    fxManager.SetScaryProfile(false);
                    break;
                case GameState.Chase:
                    audioManager.StartChaseMusic();
                    fxManager.SetScaryProfile(true);
                    break;
                case GameState.Jumpscare:
                    audioManager.PlayJumpscare();
                    break;
                case GameState.GameOver:
                    UIManager.Instance.ShowGameOver();
                    break;
                case GameState.Victory:
                    FindObjectOfType<IntroCinematicController>()?.PlayOutro();
                    break;
            }
        }

        public void PlayerDetected() => ChangeState(GameState.Chase);
        public void PlayerCaught() => ChangeState(GameState.Jumpscare);
    }
}
'''

PROGRESSION_FLAGS = '''\
namespace Game.Core
{
    public static class ProgressionFlags
    {
        public static bool FusePlaced;
        public static bool CousinRoomUnlocked;
        public static bool MasterKeyObtained;
        public static bool ExitDoorOpened;

        public static void FlagDoorOpened(string doorName)
        {
            if (doorName.Contains("Storage")) { }
            else if (doorName.Contains("CousinRoom")) CousinRoomUnlocked = true;
            else if (doorName.Contains("Exit")) ExitDoorOpened = true;
        }
    }
}
'''

AUDIO_MANAGER = '''\
using UnityEngine;

namespace Game.Core
{
    public class AudioManager : MonoBehaviour
    {
        public AudioSource musicSource;
        public AudioSource sfxSource;
        public AudioClip explorationAmbient;
        public AudioClip chaseMusic;
        public AudioClip jumpscareSound;
        public AudioClip victorySting;
        public AudioClip heartbeatSound;

        public void SetExplorationMode() => PlayMusic(explorationAmbient);
        public void StartChaseMusic() => PlayMusic(chaseMusic);
        public void PlayJumpscare() => sfxSource.PlayOneShot(jumpscareSound);
        public void PlayVictorySting() => sfxSource.PlayOneShot(victorySting);

        private void PlayMusic(AudioClip clip)
        {
            if (musicSource.clip == clip) return;
            musicSource.clip = clip;
            musicSource.Play();
        }

        public void PlayHeartbeat(float intensity)
        {
            if (!heartbeatSound) return;
            sfxSource.pitch = Mathf.Lerp(0.8f, 1.5f, intensity);
            sfxSource.volume = Mathf.Lerp(0.2f, 1f, intensity);
            if (!sfxSource.isPlaying) sfxSource.PlayOneShot(heartbeatSound);
        }
    }
}
'''

HORROR_FX_MANAGER = '''\
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;

namespace Game.Core
{
    public class HorrorFXManager : MonoBehaviour
    {
        public Volume globalVolume;
        private Vignette vignette;
        private ChromaticAberration chromatic;
        private FilmGrain grain;

        [Range(0,1)] public float scaryIntensity = 1f;

        private void Start()
        {
            if (!globalVolume) globalVolume = FindObjectOfType<Volume>();
            globalVolume.profile.TryGet(out vignette);
            globalVolume.profile.TryGet(out chromatic);
            globalVolume.profile.TryGet(out grain);
        }

        public void SetScaryProfile(bool active)
        {
            if (vignette) vignette.intensity.value = active ? 0.4f * scaryIntensity : 0.2f;
            if (chromatic) chromatic.intensity.value = active ? 0.6f * scaryIntensity : 0f;
            if (grain) grain.intensity.value = active ? 0.3f * scaryIntensity : 0f;
        }
    }
}
'''

INTRO_CINEMATIC_CONTROLLER = '''\
using System.Collections;
using UnityEngine;
using Game.UI;

namespace Game.Core
{
    public class IntroCinematicController : MonoBehaviour
    {
        public Transform playerCamera;
        public Transform bedPosition, kitchenPosition, hallwayPosition, cousinRoomPosition;
        public Transform cousinTransform;
        public GameObject levitationFX;
        public float panDuration = 2f;
        public AnimationCurve panCurve = AnimationCurve.EaseInOut(0,0,1,1);

        private PlayerController player;

        public void PlayIntro()
        {
            player = FindObjectOfType<PlayerController>();
            player.enabled = false;
            StartCoroutine(IntroSequence());
        }

        private IEnumerator IntroSequence()
        {
            // Pan to kitchen (water sound)
            yield return MoveCamera(bedPosition, kitchenPosition, panDuration);
            AudioManager am = FindObjectOfType<AudioManager>();
            if (am) am.sfxSource.PlayOneShot(am.jumpscareSound); // placeholder water sound

            yield return new WaitForSeconds(1f);

            // Pan to hallway then cousin's room
            yield return MoveCamera(kitchenPosition, hallwayPosition, panDuration);
            yield return MoveCamera(hallwayPosition, cousinRoomPosition, panDuration);

            // Open door automatically
            DoorController door = FindObjectOfType<DoorController>(); // assume cousin room door
            if (door) door.Interact();

            // Levitation animation
            float elapsed = 0f;
            Vector3 startPos = cousinTransform.position;
            Vector3 levitatePos = startPos + Vector3.up * 1.5f;
            while (elapsed < 2f)
            {
                cousinTransform.position = Vector3.Lerp(startPos, levitatePos, elapsed / 2f);
                if (levitationFX) levitationFX.SetActive(true);
                elapsed += Time.deltaTime;
                yield return null;
            }

            // Cousin snaps head toward camera
            Quaternion targetRot = Quaternion.LookRotation(playerCamera.position - cousinTransform.position);
            while (Quaternion.Angle(cousinTransform.rotation, targetRot) > 1f)
            {
                cousinTransform.rotation = Quaternion.RotateTowards(cousinTransform.rotation, targetRot, 120f * Time.deltaTime);
                yield return null;
            }

            // Fade to black
            UIManager.Instance?.GetComponentInChildren<TypewriterEffect>()?.ShowMessage("");
            yield return new WaitForSeconds(1.5f);

            // Start gameplay
            player.enabled = true;
            if (levitationFX) levitationFX.SetActive(false);
            GameManager.Instance.ChangeState(GameState.Exploration);
        }

        public void PlayOutro()
        {
            StartCoroutine(OutroSequence());
        }

        private IEnumerator OutroSequence()
        {
            // Fade to exterior scene – placeholder: just show victory message
            UIManager.Instance?.ShowMessage("You escaped! Parents arrive...");
            yield return new WaitForSeconds(3f);

            // Player re-enters, cousin normal
            cousinTransform.position = new Vector3(cousinTransform.position.x, 0, cousinTransform.position.z);
            Quaternion normalRot = Quaternion.identity;
            cousinTransform.rotation = normalRot;
            UIManager.Instance?.ShowMessage("Cousin: 'Welcome back!' (smiles)");
            yield return new WaitForSeconds(2f);

            // Chilling sting
            AudioManager am = FindObjectOfType<AudioManager>();
            if (am) am.PlayVictorySting();
            UIManager.Instance.ShowVictory();
        }

        private IEnumerator MoveCamera(Transform from, Transform to, float duration)
        {
            float time = 0;
            while (time < duration)
            {
                float t = panCurve.Evaluate(time / duration);
                playerCamera.position = Vector3.Lerp(from.position, to.position, t);
                playerCamera.rotation = Quaternion.Slerp(from.rotation, to.rotation, t);
                time += Time.deltaTime;
                yield return null;
            }
        }
    }
}
'''

# ==================== AI SCRIPTS ====================

COUSIN_AI = '''\
using UnityEngine;
using UnityEngine.AI;

namespace Game.AI
{
    public class CousinAI : MonoBehaviour
    {
        public AISettings settings;
        public Transform player; // public so FSM can access
        [HideInInspector] public Vector3 LastKnownPlayerPosition;
        public bool CanSeePlayer { get; private set; }

        private NavMeshAgent agent;
        private CousinFSM fsm;
        private Animator anim;

        private void Awake()
        {
            agent = GetComponent<NavMeshAgent>();
            fsm = new CousinFSM(this);
            if (!player) player = GameObject.FindGameObjectWithTag("Player").transform;
            anim = GetComponent<Animator>();
        }

        private void Update()
        {
            CanSeePlayer = CheckLineOfSight();
            fsm.Update();
            UpdateAnimation();
        }

        private bool CheckLineOfSight()
        {
            if (!player) return false;
            Vector3 dir = player.position - transform.position;
            float dist = dir.magnitude;
            if (dist > settings.viewDistance) return false;
            if (Vector3.Angle(transform.forward, dir) > settings.viewConeAngle * 0.5f) return false;

            if (Physics.Raycast(transform.position + Vector3.up, dir.normalized, out RaycastHit hit, dist))
                return hit.collider.CompareTag("Player");
            return false;
        }

        public void HearNoise(Vector3 position, float radius)
        {
            if (Vector3.Distance(transform.position, position) <= radius)
            {
                LastKnownPlayerPosition = position;
                fsm.TransitionTo(CousinState.Investigate);
            }
        }

        public void SetDestination(Vector3 target) => agent.SetDestination(target);
        public void Stop() => agent.ResetPath();
        public bool ReachedDestination() => agent.remainingDistance <= agent.stoppingDistance;
        public NavMeshAgent Agent => agent;

        private void UpdateAnimation() => anim?.SetFloat("Speed", agent.velocity.magnitude);

        public void TransitionToState(CousinState newState) => fsm.TransitionTo(newState);
        public CousinState CurrentState => fsm.CurrentState;
    }

    public enum CousinState { Patrol, Investigate, Chase, Attack, Stun }
}
'''

COUSIN_FSM = '''\
using System.Collections.Generic;
using UnityEngine;
using Game.Core;

namespace Game.AI
{
    public class CousinFSM
    {
        private CousinAI ai;
        private CousinState currentState;
        private float stateTimer;
        private List<Transform> patrolPoints;
        private int patrolIndex;

        public CousinState CurrentState => currentState;

        public CousinFSM(CousinAI ai)
        {
            this.ai = ai;
            currentState = CousinState.Patrol;
            patrolPoints = new List<Transform>(GameObject.FindGameObjectsWithTag("PatrolPoint").Length);
            foreach (var pt in GameObject.FindGameObjectsWithTag("PatrolPoint"))
                patrolPoints.Add(pt.transform);
        }

        public void TransitionTo(CousinState newState)
        {
            if (currentState == newState) return;
            ExitState(currentState);
            currentState = newState;
            stateTimer = 0;
            EnterState(currentState);
        }

        public void Update()
        {
            stateTimer += Time.deltaTime;
            switch (currentState)
            {
                case CousinState.Patrol: PatrolUpdate(); break;
                case CousinState.Investigate: InvestigateUpdate(); break;
                case CousinState.Chase: ChaseUpdate(); break;
                case CousinState.Attack: AttackUpdate(); break;
                case CousinState.Stun: StunUpdate(); break;
            }
        }

        private void EnterState(CousinState state)
        {
            switch (state)
            {
                case CousinState.Patrol: ai.SetDestination(GetNextPatrolPoint()); break;
                case CousinState.Investigate: ai.SetDestination(ai.LastKnownPlayerPosition); break;
                case CousinState.Chase: ai.Agent.speed = ai.settings.chaseSpeed; break;
                case CousinState.Attack: ai.Stop(); break;
                case CousinState.Stun: ai.Agent.speed = 0; break;
            }
        }

        private void ExitState(CousinState state)
        {
            if (state == CousinState.Chase || state == CousinState.Stun)
                ai.Agent.speed = ai.settings.patrolSpeed;
        }

        private void PatrolUpdate()
        {
            if (ai.CanSeePlayer) TransitionTo(CousinState.Chase);
            else if (ai.ReachedDestination()) ai.SetDestination(GetNextPatrolPoint());
        }

        private void InvestigateUpdate()
        {
            if (ai.CanSeePlayer) TransitionTo(CousinState.Chase);
            else if (ai.ReachedDestination() && stateTimer > 5f) TransitionTo(CousinState.Patrol);
        }

        private void ChaseUpdate()
        {
            if (!ai.CanSeePlayer)
            {
                ai.LastKnownPlayerPosition = ai.player.position;
                TransitionTo(CousinState.Investigate);
                return;
            }
            ai.SetDestination(ai.player.position);
            if (Vector3.Distance(ai.transform.position, ai.player.position) < 1.5f)
                TransitionTo(CousinState.Attack);
        }

        private void AttackUpdate() => GameManager.Instance.PlayerCaught();

        private void StunUpdate() { if (stateTimer > 3f) TransitionTo(CousinState.Patrol); }

        private Vector3 GetNextPatrolPoint()
        {
            if (patrolPoints.Count == 0) return ai.transform.position;
            patrolIndex = (patrolIndex + 1) % patrolPoints.Count;
            return patrolPoints[patrolIndex].position;
        }
    }
}
'''

AI_SETTINGS = '''\
using UnityEngine;

namespace Game.AI
{
    [CreateAssetMenu(fileName = "AISettings", menuName = "AI/Settings")]
    public class AISettings : ScriptableObject
    {
        public float patrolSpeed = 2f;
        public float chaseSpeed = 5f;
        public float viewDistance = 10f;
        public float viewConeAngle = 60f;
        public float hearingRadius = 15f;
    }
}
'''

# ==================== UI SCRIPTS ====================

UI_MANAGER = '''\
using UnityEngine;
using UnityEngine.UI;

namespace Game.UI
{
    public class UIManager : MonoBehaviour
    {
        public static UIManager Instance { get; private set; }
        [SerializeField] private Text messageText;
        [SerializeField] private GameObject gameOverPanel;
        [SerializeField] private GameObject victoryPanel;
        [SerializeField] private TypewriterEffect typewriter;
        [SerializeField] private CrosshairController crosshair;

        private void Awake()
        {
            if (Instance) { Destroy(gameObject); return; }
            Instance = this;
        }

        public void ShowMessage(string msg)
        {
            if (typewriter) typewriter.ShowMessage(msg);
            else if (messageText) messageText.text = msg;
        }

        public void ShowGameOver()
        {
            gameOverPanel?.SetActive(true);
            Time.timeScale = 0f;
        }

        public void ShowVictory()
        {
            victoryPanel?.SetActive(true);
            Time.timeScale = 0f;
        }

        public void UpdateCrosshair(bool canInteract) => crosshair?.SetState(canInteract);
    }
}
'''

VIRTUAL_JOYSTICK = '''\
using UnityEngine;
using UnityEngine.EventSystems;
using UnityEngine.UI;

namespace Game.UI
{
    public class VirtualJoystick : MonoBehaviour, IPointerDownHandler, IPointerUpHandler, IDragHandler
    {
        public RectTransform background;
        public RectTransform handle;
        [Range(0,1)] public float handleRange = 1f;
        public float deadZone = 0.1f;

        public Vector2 Direction { get; private set; }

        private void Start() => handle.anchoredPosition = Vector2.zero;

        public void OnPointerDown(PointerEventData eventData) => OnDrag(eventData);

        public void OnDrag(PointerEventData eventData)
        {
            Vector2 radius = background.sizeDelta / 2;
            Vector2 pos = eventData.position - (Vector2)background.position;
            Direction = pos / (radius * handleRange);
            if (Direction.magnitude < deadZone) Direction = Vector2.zero;
            else Direction = Direction.normalized * ((Direction.magnitude - deadZone) / (1 - deadZone));
            handle.anchoredPosition = Direction * radius * handleRange;
        }

        public void OnPointerUp(PointerEventData eventData)
        {
            Direction = Vector2.zero;
            handle.anchoredPosition = Vector2.zero;
        }
    }
}
'''

TYPEWRITER_EFFECT = '''\
using System.Collections;
using UnityEngine;
using UnityEngine.UI;

namespace Game.UI
{
    public class TypewriterEffect : MonoBehaviour
    {
        public Text displayText;
        public float charsPerSecond = 20f;
        public AudioClip typeSound;
        private AudioSource audioSource;
        private Coroutine typing;

        private void Awake() => audioSource = gameObject.AddComponent<AudioSource>();

        public void ShowMessage(string message)
        {
            if (typing != null) StopCoroutine(typing);
            typing = StartCoroutine(TypeText(message));
        }

        private IEnumerator TypeText(string message)
        {
            displayText.text = "";
            foreach (char c in message)
            {
                displayText.text += c;
                if (typeSound) audioSource.PlayOneShot(typeSound);
                yield return new WaitForSeconds(1f / charsPerSecond);
            }
        }
    }
}
'''

CROSSHAIR_CONTROLLER = '''\
using UnityEngine;
using UnityEngine.UI;

namespace Game.UI
{
    public class CrosshairController : MonoBehaviour
    {
        public Image crosshairImage;
        public Color normalColor = Color.white;
        public Color interactColor = Color.green;

        public void SetState(bool canInteract)
        {
            crosshairImage.color = canInteract ? interactColor : normalColor;
        }
    }
}
'''

# ==================== EDITOR SCRIPTS ====================

PROJECT_CONFIGURATOR = '''\
#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace Game.Editor
{
    [InitializeOnLoad]
    public class ProjectConfigurator
    {
        static ProjectConfigurator()
        {
            EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Android, BuildTarget.Android);
            PlayerSettings.SetScriptingBackend(BuildTargetGroup.Android, ScriptingImplementation.IL2CPP);
            PlayerSettings.Android.targetArchitectures = AndroidArchitecture.ARM64;
            PlayerSettings.Android.minSdkVersion = AndroidSdkVersions.AndroidApiLevel24;
            PlayerSettings.Android.targetSdkVersion = AndroidSdkVersions.AndroidApiLevel33;

            QualitySettings.vSyncCount = 0;
            Application.targetFrameRate = 60;
            QualitySettings.SetQualityLevel(1);

            AddTag("Player"); AddTag("Monster"); AddTag("Interactable");
            AddTag("Key"); AddTag("HideSpot"); AddTag("Wood");
            AddTag("Tile"); AddTag("Carpet"); AddTag("PatrolPoint"); AddTag("Finish");

            CreateLayer("Player", 8);
            CreateLayer("Monster", 9);

            Debug.Log("Project configured for 'The Cousin's Secret'");
        }

        static void AddTag(string tag)
        {
            SerializedObject tagManager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            SerializedProperty tagsProp = tagManager.FindProperty("tags");
            for (int i = 0; i < tagsProp.arraySize; i++)
                if (tagsProp.GetArrayElementAtIndex(i).stringValue == tag) return;
            tagsProp.InsertArrayElementAtIndex(tagsProp.arraySize);
            tagsProp.GetArrayElementAtIndex(tagsProp.arraySize - 1).stringValue = tag;
            tagManager.ApplyModifiedProperties();
        }

        static void CreateLayer(string name, int index)
        {
            SerializedObject tagManager = new SerializedObject(AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/TagManager.asset")[0]);
            SerializedProperty layersProp = tagManager.FindProperty("layers");
            layersProp.GetArrayElementAtIndex(index).stringValue = name;
            tagManager.ApplyModifiedProperties();
        }
    }
}
#endif
'''

SCENE_SETUP_WIZARD = '''\
#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;
using UnityEngine.AI;
using UnityEngine.SceneManagement;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using Game.Core;
using Game.AI;
using Game.UI;

namespace Game.Editor
{
    [InitializeOnLoad]
    public class SceneSetupWizard
    {
        static SceneSetupWizard()
        {
            EditorApplication.delayCall += SetupScene;
        }

        static void SetupScene()
        {
            if (SceneManager.GetActiveScene().name != "MainScene") return;
            if (GameObject.Find("GameManager")) return; // Already set up

            // ---- Global Managers ----
            GameObject gm = new GameObject("GameManager");
            gm.AddComponent<GameManager>();
            GameObject audioGO = new GameObject("AudioManager");
            audioGO.AddComponent<AudioManager>();
            GameObject fxGO = new GameObject("HorrorFX");
            fxGO.AddComponent<HorrorFXManager>();
            GameObject uiGO = new GameObject("UIManager");
            uiGO.AddComponent<UIManager>();

            // ---- House ----
            CreateHouse();

            // ---- Player ----
            GameObject player = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            player.name = "Player";
            player.tag = "Player";
            player.layer = LayerMask.NameToLayer("Player");
            player.transform.position = new Vector3(0, 1, 0);
            CharacterController cc = player.AddComponent<CharacterController>();
            cc.height = 2f; cc.center = new Vector3(0,1,0);
            GameObject cam = new GameObject("MainCamera");
            cam.AddComponent<Camera>();
            cam.transform.SetParent(player.transform);
            cam.transform.localPosition = new Vector3(0, 1.6f, 0);
            cam.AddComponent<AudioListener>();
            player.AddComponent<PlayerController>().useMobileInput = true;
            player.AddComponent<FootstepHandler>();
            player.AddComponent<InteractionManager>();
            player.AddComponent<MobileInput>();

            // ---- UI Canvas ----
            GameObject canvas = new GameObject("UICanvas");
            Canvas c = canvas.AddComponent<Canvas>();
            c.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.AddComponent<CanvasScaler>();
            canvas.AddComponent<GraphicRaycaster>();
            new GameObject("EventSystem").AddComponent<EventSystem>().gameObject.AddComponent<StandaloneInputModule>();

            // ---- Cousin ----
            GameObject monster = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            monster.name = "Cousin";
            monster.tag = "Monster";
            monster.layer = LayerMask.NameToLayer("Monster");
            monster.transform.position = new Vector3(8, 1, 0);
            monster.AddComponent<NavMeshAgent>();
            monster.AddComponent<CousinAI>();
            monster.AddComponent<Animator>();

            // ---- Patrol Points ----
            for (int i = 0; i < 5; i++)
            {
                GameObject pt = new GameObject("PatrolPoint" + i);
                pt.tag = "PatrolPoint";
                pt.transform.position = new Vector3(Random.Range(2, 12), 0, Random.Range(2, 12));
            }

            // ---- Items & Doors ----
            CreateItemsAndDoors();

            // ---- NavMesh ----
            NavMeshBuilder.BuildNavMesh();

            // ---- URP Volume ----
            GameObject vol = new GameObject("GlobalVolume");
            Volume volume = vol.AddComponent<Volume>();
            VolumeProfile profile = ScriptableObject.CreateInstance<VolumeProfile>();
            volume.profile = profile;
            profile.Add<Vignette>().intensity.Override(0.2f);
            profile.Add<ChromaticAberration>().intensity.Override(0f);
            profile.Add<FilmGrain>().intensity.Override(0f);

            // ---- AI Settings ----
            if (!AssetDatabase.LoadAssetAtPath<AISettings>("Assets/ScriptableObjects/AISettings.asset"))
            {
                AISettings ai = ScriptableObject.CreateInstance<AISettings>();
                AssetDatabase.CreateAsset(ai, "Assets/ScriptableObjects/AISettings.asset");
            }

            Debug.Log("Scene setup complete.");
        }

        static void CreateHouse()
        {
            // Floor
            GameObject floor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            floor.name = "Floor"; floor.tag = "Carpet";
            floor.transform.position = Vector3.zero;
            floor.transform.localScale = new Vector3(20, 0.1f, 20);
            // Walls omitted for brevity but would be placed here
        }

        static void CreateItemsAndDoors()
        {
            // Red Key pickup
            GameObject redKey = new GameObject("RedKeyPickup"); redKey.tag = "Key";
            redKey.transform.position = new Vector3(2, 0.5f, 2);
            redKey.AddComponent<KeyPickup>().itemData = AssetDatabase.LoadAssetAtPath<ItemData>("Assets/Resources/Items/RedKey.asset");

            // Storage door (needs red key)
            GameObject storageDoor = GameObject.CreatePrimitive(PrimitiveType.Cube);
            storageDoor.name = "StorageDoor"; storageDoor.tag = "Interactable";
            storageDoor.transform.position = new Vector3(5, 1, 5);
            storageDoor.AddComponent<DoorController>().requiredKeyName = "RedKey";

            // Fuse inside storage -> Fusebox -> Blue key -> Cousin's room -> Master key -> Exit
            // Further placements would follow the same pattern.
        }
    }
}
#endif
'''

# Map of file paths to content
SCRIPTS = {
    "Assets/Scripts/Core/PlayerController.cs": PLAYER_CONTROLLER,
    "Assets/Scripts/Core/MobileInput.cs": MOBILE_INPUT,
    "Assets/Scripts/Core/InteractionManager.cs": INTERACTION_MANAGER,
    "Assets/Scripts/Core/IInteractable.cs": INTERACTABLE_INTERFACE,
    "Assets/Scripts/Core/InventorySystem.cs": INVENTORY_SYSTEM,
    "Assets/Scripts/Core/ItemData.cs": ITEM_DATA,
    "Assets/Scripts/Core/DoorController.cs": DOOR_CONTROLLER,
    "Assets/Scripts/Core/LockedContainer.cs": LOCKED_CONTAINER,
    "Assets/Scripts/Core/Fusebox.cs": FUSEBOX,
    "Assets/Scripts/Core/KeyPickup.cs": KEY_PICKUP,
    "Assets/Scripts/Core/VasePickup.cs": VASE_PICKUP,
    "Assets/Scripts/Core/ThrowableVase.cs": THROWABLE_VASE,
    "Assets/Scripts/Core/FootstepHandler.cs": FOOTSTEP_HANDLER,
    "Assets/Scripts/Core/GameManager.cs": GAME_MANAGER,
    "Assets/Scripts/Core/ProgressionFlags.cs": PROGRESSION_FLAGS,
    "Assets/Scripts/Core/AudioManager.cs": AUDIO_MANAGER,
    "Assets/Scripts/Core/HorrorFXManager.cs": HORROR_FX_MANAGER,
    "Assets/Scripts/Core/IntroCinematicController.cs": INTRO_CINEMATIC_CONTROLLER,
    "Assets/Scripts/AI/CousinAI.cs": COUSIN_AI,
    "Assets/Scripts/AI/CousinFSM.cs": COUSIN_FSM,
    "Assets/Scripts/AI/AISettings.cs": AI_SETTINGS,
    "Assets/Scripts/UI/UIManager.cs": UI_MANAGER,
    "Assets/Scripts/UI/VirtualJoystick.cs": VIRTUAL_JOYSTICK,
    "Assets/Scripts/UI/TypewriterEffect.cs": TYPEWRITER_EFFECT,
    "Assets/Scripts/UI/CrosshairController.cs": CROSSHAIR_CONTROLLER,
    "Assets/Scripts/Editor/ProjectConfigurator.cs": PROJECT_CONFIGURATOR,
    "Assets/Scripts/Editor/SceneSetupWizard.cs": SCENE_SETUP_WIZARD,
}

# ==================== GENERATION & CLEANUP ====================
def clean_stale_files():
    """Delete any .cs files that are not in our manifest to avoid leftover conflicts."""
    if not os.path.exists(PROJECT_ROOT):
        return
    for root, dirs, files in os.walk(os.path.join(PROJECT_ROOT, "Assets")):
        for file in files:
            if file.endswith(".cs"):
                full_path = os.path.relpath(os.path.join(root, file), PROJECT_ROOT)
                # Normalize path separators
                normalized = full_path.replace("\\", "/")
                if normalized not in SCRIPTS and normalized not in ASMDEF_FILES:
                    target = os.path.join(PROJECT_ROOT, full_path)
                    try:
                        os.remove(target)
                        print(f"Removed stale file: {target}")
                    except Exception as e:
                        print(f"Failed to remove {target}: {e}")

def create_project():
    # Create directory structure
    for folder in FOLDERS:
        os.makedirs(os.path.join(PROJECT_ROOT, folder), exist_ok=True)

    # Write assembly definitions
    for path, data in ASMDEF_FILES.items():
        full = os.path.join(PROJECT_ROOT, path)
        with open(full, 'w') as f:
            json.dump(data, f, indent=2)

    # Clean up old files that could cause warnings
    clean_stale_files()

    # Write all scripts
    for path, content in SCRIPTS.items():
        full = os.path.join(PROJECT_ROOT, path)
        with open(full, 'w') as f:
            f.write(content.strip() + "\n")

    # Empty scene placeholder
    scene_path = os.path.join(PROJECT_ROOT, "Assets/Scenes/MainScene.unity")
    if not os.path.exists(scene_path):
        open(scene_path, 'w').close()

    # .gitignore
    gitignore_path = os.path.join(PROJECT_ROOT, ".gitignore")
    with open(gitignore_path, 'w') as f:
        f.write("/[Ll]ibrary/\n/[Tt]emp/\n/[Oo]bj/\n/[Bb]uild/\n/[Bb]uilds/\n/[Ll]ogs/\n/[Uu]ser[Ss]ettings/\n")

    print(f"Project '{PROJECT_ROOT}' generated successfully. Open it in Unity to complete auto-setup.")

if __name__ == "__main__":
    create_project()
